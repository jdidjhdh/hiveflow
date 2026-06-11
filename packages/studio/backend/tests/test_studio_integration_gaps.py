"""Integration tests for Studio engine_service gaps (KB, HITL, checkpoint, guards)."""
import asyncio

import pytest
import pytest_asyncio

from hiveflow import AbortExecutionException
from hiveflow.rag import Document, DocumentType

from app.core.engine_service import EngineService


@pytest_asyncio.fixture
async def engine():
    svc = EngineService()
    await svc.start()
    yield svc
    await svc.shutdown()


@pytest.mark.asyncio
async def test_kb_manager_create_and_search(engine):
    mgr = engine.get_kb_manager()
    await mgr.create_kb("kb_test", "Test KB", "desc")
    kbs = await mgr.list_kbs()
    assert any(k.kb_id == "kb_test" for k in kbs)

    doc = Document(
        doc_id=Document.compute_doc_id("HiveFlow orchestrator", "text"),
        content="HiveFlow is an orchestrator for multi-agent workflows.",
        doc_type=DocumentType.TEXT,
    )
    await mgr.add_document("kb_test", doc)
    kb = mgr.get_kb("kb_test")
    assert kb is not None
    assert kb.doc_count >= 1

    results = await mgr.search("kb_test", "orchestrator", top_k=3)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_hitl_blocks_until_approved(engine):
    wf_id = "wf_hitl_ok"

    async def pass_task(deps, view):
        return {"ok": True}

    graph = {
        "approve_step": {
            "task": pass_task,
            "depends_on": [],
            "variant": "hitl",
            "hitl_config": {
                "prompt": "Approve?",
                "action": "approval",
                "timeout_seconds": 5,
                "on_timeout": "fail",
            },
        },
    }

    async def run_flow():
        task = asyncio.create_task(
            engine.execute_workflow(wf_id, graph, enable_guard=False)
        )
        await asyncio.sleep(0.3)
        pending = await engine.get_hitl_manager().list_pending_gates(wf_id)
        assert len(pending) == 1
        await engine.get_hitl_manager().respond(pending[0].gate_id, approved=True)
        return await task

    result = await asyncio.wait_for(run_flow(), timeout=8)
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_hitl_reject_aborts(engine):
    wf_id = "wf_hitl_no"

    async def pass_task(deps, view):
        return {"ok": True}

    graph = {
        "gate": {
            "task": pass_task,
            "depends_on": [],
            "variant": "hitl",
            "hitl_config": {"prompt": "Reject", "timeout_seconds": 5},
        },
    }

    async def run_flow():
        task = asyncio.create_task(
            engine.execute_workflow(wf_id, graph, enable_guard=False)
        )
        await asyncio.sleep(0.3)
        pending = await engine.get_hitl_manager().list_pending_gates(wf_id)
        await engine.get_hitl_manager().respond(pending[0].gate_id, approved=False)
        return await task

    result = await run_flow()
    assert result["status"] == "aborted"


@pytest.mark.asyncio
async def test_checkpoint_on_node_complete(engine):
    wf_id = "wf_cp"

    async def task_a(deps, view):
        return {"a": 1}

    graph = {"a": {"task": task_a, "depends_on": []}}
    result = await engine.execute_workflow(
        wf_id, graph, enable_guard=False, enable_checkpoint=True
    )
    assert result["status"] == "completed"
    cps = await engine.get_checkpoint_manager().list_checkpoints(wf_id)
    assert len(cps) >= 1


def test_input_guard_blocks_sql_injection():
    from hiveflow import InputGuard

    svc = EngineService()
    svc._input_guard = InputGuard()
    with pytest.raises(AbortExecutionException):
        svc._apply_input_guard({"payload": "DROP TABLE users"})
