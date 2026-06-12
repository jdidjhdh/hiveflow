"""Tests for ExecutionBackend abstraction."""

import pytest

from hiveflow import MemoryBlackboard, SecureBlackboard
from hiveflow.execution import (
    ExecutionBackendNotReadyError,
    GraphExecutionResult,
    LangGraphExecutionBackend,
    NativeExecutionBackend,
    get_execution_backend,
)
from hiveflow.orchestrator import DynamicOrchestrator

SAMPLE_PLAN = {
    "research": {"task": "search", "depends_on": []},
    "final_answer": {"task": "summarize", "depends_on": ["research"]},
}


@pytest.mark.asyncio
async def test_native_backend_executes_graph():
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(bb)
    backend = NativeExecutionBackend(orch)

    async def research(_deps, _view):
        return {"findings": "ok"}

    async def summarize(deps, _view):
        return {"answer": deps["research"]["findings"]}

    graph = {
        "research": {"depends_on": [], "task": research},
        "final_answer": {"depends_on": ["research"], "task": summarize},
    }

    result = await backend.execute(graph, context={"trace_id": "t-1"})
    assert isinstance(result, GraphExecutionResult)
    assert result.backend == "native"
    assert result.status == "completed"
    assert result.results["research"]["findings"] == "ok"
    assert result.results["final_answer"]["answer"] == "ok"
    assert result.metadata["context"]["trace_id"] == "t-1"


def test_get_execution_backend_native_requires_orchestrator():
    with pytest.raises(ValueError, match="orchestrator"):
        get_execution_backend("native")


def test_get_execution_backend_unknown():
    bb = SecureBlackboard(MemoryBlackboard())
    with pytest.raises(ValueError, match="Unknown"):
        get_execution_backend("unknown", orchestrator=DynamicOrchestrator(bb))


def test_langgraph_backend_export_spec():
    backend = LangGraphExecutionBackend()
    spec = backend.to_langgraph_spec(SAMPLE_PLAN, workflow_id="sidecar_demo")
    assert spec["workflow_id"] == "sidecar_demo"
    assert spec["entry_point"] == "research"
    assert any(n["id"] == "final_answer" for n in spec["nodes"])


@pytest.mark.asyncio
async def test_langgraph_backend_execute_raises_not_ready():
    backend = LangGraphExecutionBackend()
    with pytest.raises(ExecutionBackendNotReadyError, match="sidecar"):
        await backend.execute({})
