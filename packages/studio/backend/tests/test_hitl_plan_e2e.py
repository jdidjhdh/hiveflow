"""End-to-end tests: plan HITL blocks query until HTTP respond with modified plan."""
import asyncio
import os

import pytest
import pytest_asyncio

os.environ.setdefault("HIVEFLOW_AGENT_ECHO_LLM", "true")


@pytest_asyncio.fixture
async def engine():
    from app.core.engine_service import EngineService

    svc = EngineService()
    await svc.start()
    yield svc
    await svc.shutdown()


MODIFIED_PLAN = {
    "general_step": {"task": "general", "depends_on": []},
    "final_answer": {"task": "summarize", "depends_on": ["general_step"]},
}


@pytest.mark.asyncio
async def test_plan_hitl_e2e_async_modify_plan(engine):
    """run_agent_query blocks until HITL respond with modified plan."""
    os.environ["HIVEFLOW_PLAN_HITL"] = "true"
    try:
        if engine._hive_mind:
            await engine.set_runtime_mode("core")
        info = await engine.set_runtime_mode("agent")
        assert info["agent_active"]
        assert engine._hive_mind.config.enable_plan_hitl is True

        query_task = asyncio.create_task(engine.run_agent_query("e2e plan hitl async"))

        gate = None
        for _ in range(100):
            pending = await engine.get_hitl_manager().list_pending_gates()
            if pending:
                gate = pending[0]
                break
            await asyncio.sleep(0.05)

        assert gate is not None
        assert gate.node_id == "plan_approval"
        assert gate.context.get("plan") is not None

        await engine.get_hitl_manager().respond(
            gate.gate_id,
            approved=True,
            modified_data={"plan": MODIFIED_PLAN},
        )

        result = await asyncio.wait_for(query_task, timeout=20)
        assert result.get("status") == "completed"
        assert "answer" in result
        assert result.get("intent_id")
    finally:
        os.environ.pop("HIVEFLOW_PLAN_HITL", None)
        await engine.set_runtime_mode("core")


@pytest.mark.asyncio
async def test_plan_hitl_e2e_reject_via_http(engine):
    """Rejected plan returns plan_rejected without executing."""
    os.environ["HIVEFLOW_PLAN_HITL"] = "true"
    try:
        if engine._hive_mind:
            await engine.set_runtime_mode("core")
        await engine.set_runtime_mode("agent")

        query_task = asyncio.create_task(engine.run_agent_query("reject me"))

        gate_id = None
        for _ in range(100):
            pending = await engine.get_hitl_manager().list_pending_gates()
            if pending:
                gate_id = pending[0].gate_id
                break
            await asyncio.sleep(0.05)

        assert gate_id
        await engine.get_hitl_manager().respond(gate_id, approved=False)

        result = await asyncio.wait_for(query_task, timeout=20)
        assert result.get("status") == "plan_rejected"
    finally:
        os.environ.pop("HIVEFLOW_PLAN_HITL", None)
        await engine.set_runtime_mode("core")


@pytest.mark.asyncio
async def test_plan_hitl_e2e_http_respond_modified_plan(async_client, initialized_engine):
    """HTTP: /api/agent/query blocks until /api/hitl respond."""
    os.environ["HIVEFLOW_PLAN_HITL"] = "true"
    os.environ["HIVEFLOW_AGENT_ECHO_LLM"] = "true"
    try:
        await async_client.post("/api/agent/runtime", json={"mode": "core"})
        await async_client.post("/api/agent/runtime", json={"mode": "agent"})

        query_task = asyncio.create_task(
            async_client.post("/api/agent/query", json={"query": "hitl e2e http async"})
        )

        gate_id = None
        for _ in range(100):
            pending = await async_client.get("/api/hitl/pending")
            if pending.status_code == 200:
                gates = pending.json().get("gates", [])
                if gates:
                    gate_id = gates[0]["gate_id"]
                    assert gates[0]["node_id"] == "plan_approval"
                    break
            await asyncio.sleep(0.05)

        assert gate_id, "Expected pending plan_approval gate"

        respond = await async_client.post(
            f"/api/hitl/{gate_id}/respond",
            json={
                "approved": True,
                "modified_data": {"plan": MODIFIED_PLAN},
                "comment": "e2e modified",
            },
        )
        assert respond.status_code == 200

        query_resp = await asyncio.wait_for(query_task, timeout=20)
        assert query_resp.status_code == 200
        data = query_resp.json()
        assert data.get("status") == "completed"
        assert data.get("intent_id")
    finally:
        os.environ.pop("HIVEFLOW_PLAN_HITL", None)
        await async_client.post("/api/agent/runtime", json={"mode": "core"})
