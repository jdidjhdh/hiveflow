"""Tests for HiveMindApp extensions: ReAct skill, plan HITL, replay."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from hiveflow import HiveFlowConfig, HITLStatus

from app import HiveMindApp, HiveMindConfig
from llm.base import LLMClient
from memory.vector_store import VectorStore
from replay import ReplayDebugger


class MockLLM(LLMClient):
    def __init__(self, json_responses=None):
        self._json = list(json_responses or [])
        self._idx = 0

    async def complete(self, messages, **kwargs):
        return "ok"

    async def complete_json(self, messages, **kwargs):
        if self._idx < len(self._json):
            r = self._json[self._idx]
            self._idx += 1
            return r
        return {}

    async def stream(self, messages, **kwargs):
        yield "ok"

    async def embed(self, texts):
        return [[0.1] * 4 for _ in texts]


class MemVS(VectorStore):
    async def add_texts(self, texts, metadatas=None, ids=None):
        return ids or []

    async def similarity_search(self, query, k=5, filter_fn=None):
        return []

    async def delete(self, ids):
        pass


def _app(json_responses):
    llm = MockLLM(json_responses)
    cfg = HiveMindConfig(
        hiveflow_config=HiveFlowConfig(blackboard_type="memory"),
        llm=llm,
        embedding_llm=llm,
        vector_store=MemVS(),
        skill_registry={"echo": "Echo skill", "summarize": "Summarize"},
        enable_result_cleanup=False,
    )
    return HiveMindApp(cfg), llm


@pytest.mark.asyncio
async def test_create_react_skill_writes_result_key():
    app, llm = _app([
        {"intent": "test", "required_skills": ["echo"], "payload": {}, "priority": "normal"},
        {"final_answer": {"task": "echo", "depends_on": []}},
    ])
    llm.complete_json = AsyncMock(side_effect=[
        {"intent": "test", "required_skills": ["echo"], "payload": {}, "priority": "normal"},
        {"final_answer": {"task": "echo", "depends_on": []}},
        {"type": "final_answer", "content": "hello react"},
    ])

    await app.start()

    from worker.tools.blackboard_tools import Tool

    class EchoTool(Tool):
        name = "echo"
        description = "echo"
        parameters = {"type": "object", "properties": {}}

        async def run(self, params, view):
            return "pong"

    await app.create_react_skill("echo", "echo-agent", tools=[EchoTool()], max_steps=3)

    async def summarize(ecm, view):
        payload = {"answer": "done"}
        await view.put(f"hivemind:result:{ecm.intent_id}", payload)
        return payload

    await app.create_skill_agent(
        "summarize", "sum", summarize,
        read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"},
    )

    # Override plan to use echo then summarize
    app.cognitive_orch.llm = llm
    result = await app.run_query("test react")
    assert result.get("status") in ("completed", None) or "answer" in result
    await app.shutdown()


@pytest.mark.asyncio
async def test_execute_plan_without_llm_planning():
    llm = MockLLM([
        {"intent": "x", "required_skills": ["summarize"], "payload": {}, "priority": "normal"},
    ])
    cfg = HiveMindConfig(
        hiveflow_config=HiveFlowConfig(blackboard_type="memory"),
        llm=llm,
        embedding_llm=llm,
        vector_store=MemVS(),
        skill_registry={"summarize": "s", "general": "g"},
        enable_result_cleanup=False,
    )
    app = HiveMindApp(cfg)

    async def summarize(ecm, view):
        payload = {"answer": "done"}
        await view.put(f"hivemind:result:{ecm.intent_id}", payload)
        return payload

    await app.start()
    await app.create_skill_agent(
        "summarize", "sum", summarize,
        read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"},
    )
    await app.create_skill_agent(
        "general", "gen", summarize,
        read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"},
    )

    plan = {
        "general_step": {"task": "general", "depends_on": []},
        "final_answer": {"task": "summarize", "depends_on": ["general_step"]},
    }
    result = await app.execute_plan(plan, "run plan")
    assert result["status"] == "completed"
    assert result.get("intent_id")
    await app.shutdown()


@pytest.mark.asyncio
async def test_plan_hitl_modified_plan():
    from orchestrator.cognitive import CognitiveOrchestrator
    from hiveflow import HITLAction

    original_plan = {
        "step_a": {"task": "summarize", "depends_on": []},
        "final_answer": {"task": "summarize", "depends_on": ["step_a"]},
    }
    modified_plan = {
        "custom_step": {"task": "summarize", "depends_on": []},
        "final_answer": {"task": "summarize", "depends_on": ["custom_step"]},
    }
    hitl = MagicMock()
    gate = MagicMock(gate_id="g2")
    hitl.create_gate = AsyncMock(return_value=gate)
    resolved = MagicMock(
        status=HITLStatus.MODIFIED,
        human_response={"plan": modified_plan},
    )
    hitl.wait_for_response = AsyncMock(return_value=resolved)

    orch = CognitiveOrchestrator(
        llm=MockLLM([]),
        hiveflow=MagicMock(),
        skill_bindings={},
        skill_signatures={"summarize": "s"},
        memory_manager=MagicMock(),
        intent_parser=MagicMock(),
        hitl_manager=hitl,
        enable_plan_hitl=True,
    )
    plan, rejection = await orch._maybe_approve_plan(original_plan, "intent-1", "conv-1")
    assert rejection is None
    assert plan == modified_plan
    hitl.create_gate.assert_called_once()
    assert hitl.create_gate.call_args.kwargs["action"] == HITLAction.REVIEW


@pytest.mark.asyncio
async def test_plan_hitl_rejection():
    llm = MockLLM([
        {"intent": "x", "required_skills": [], "payload": {}, "priority": "normal"},
        {"final_answer": {"task": "summarize", "depends_on": []}},
    ])
    hitl = MagicMock()
    gate = MagicMock(gate_id="g1")
    hitl.create_gate = AsyncMock(return_value=gate)
    resolved = MagicMock(status=HITLStatus.REJECTED, human_response=None)
    hitl.wait_for_response = AsyncMock(return_value=resolved)

    cfg = HiveMindConfig(
        hiveflow_config=HiveFlowConfig(blackboard_type="memory"),
        llm=llm,
        embedding_llm=llm,
        vector_store=MemVS(),
        skill_registry={"summarize": "s"},
        enable_plan_hitl=True,
        hitl_manager=hitl,
        enable_result_cleanup=False,
    )
    app = HiveMindApp(cfg)
    await app.start()
    result = await app.run_query("plan me")
    assert result["status"] == "plan_rejected"
    await app.shutdown()


def test_replay_debugger_audit_timeline():
    bb = MagicMock()
    bb._audit_log = [
        {"agent": "a1", "key": "k1", "action": "put", "timestamp": 1.0},
        {"agent": "a2", "key": "k2", "action": "get", "timestamp": 2.0},
    ]
    dbg = ReplayDebugger(bb)
    rows = dbg.get_audit_timeline(agent="a1")
    assert len(rows) == 1
    session = dbg.build_replay_session("intent-1")
    assert session["intent_id"] == "intent-1"
