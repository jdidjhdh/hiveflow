import asyncio
from graphlib import TopologicalSorter

import pytest

from hiveflow import DAGOrchestrator
from hiveflow.blackboard import MemoryBlackboard, SecureBlackboard


@pytest.mark.asyncio
async def test_dag_sort_basic():
    graph = {
        "B": {"depends_on": ["A"]},
        "C": {"depends_on": ["A"]},
        "A": {"depends_on": []},
        "D": {"depends_on": ["B", "C"]},
    }
    sorter = TopologicalSorter({node: data.get("depends_on", []) for node, data in graph.items()})
    result = list(sorter.static_order())
    # A must come before B, C, D
    assert result.index("A") < result.index("D")


@pytest.mark.asyncio
async def test_dag_cycle_detection():
    graph = {
        "A": {"depends_on": ["B"]},
        "B": {"depends_on": ["A"]},
    }
    sorter = TopologicalSorter({node: data.get("depends_on", []) for node, data in graph.items()})
    with pytest.raises(ValueError):
        list(sorter.static_order())


@pytest.mark.asyncio
async def test_dag_parallel_execution():
    graph = {
        "A": {"depends_on": []},
        "B": {"depends_on": []},
        "C": {"depends_on": []},
    }
    sorter = TopologicalSorter({node: data.get("depends_on", []) for node, data in graph.items()})
    sorter.prepare()
    ready = []
    while sorter.is_active():
        batch = list(sorter.get_ready())
        if not batch:
            break
        ready.extend(batch)
        for node in batch:
            sorter.done(node)
    assert set(ready) == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_dag_orchestrator():
    results = {}

    async def node_a(deps, view):
        results["A"] = "done_a"
        return "done_a"

    async def node_b(deps, view):
        results["B"] = f"after_{deps['A']}"
        return results["B"]

    graph = {
        "A": {"task": node_a, "depends_on": []},
        "B": {"task": node_b, "depends_on": ["A"]},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["A"] == "done_a"
    assert result["B"] == "after_done_a"


@pytest.mark.asyncio
async def test_dag_orchestrator_hitl_approval():
    from hiveflow import HITLAction, HITLManager

    hitl = HITLManager()
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, hitl_manager=hitl, workflow_id="wf_hitl")

    async def gated_task(deps, view):
        return "executed"

    graph = {
        "gate": {
            "task": gated_task,
            "depends_on": [],
            "hitl": {
                "action": HITLAction.APPROVAL.value,
                "prompt": "Approve?",
                "context": {"step": 1},
            },
        },
    }

    exec_task = asyncio.create_task(orch.execute(graph))
    await asyncio.sleep(0.05)
    pending = await hitl.list_pending_gates()
    assert len(pending) == 1
    await hitl.respond(pending[0].gate_id, approved=True)

    result = await exec_task
    assert result["gate"] == "executed"


@pytest.mark.asyncio
async def test_dag_orchestrator_hitl_rejection_aborts():
    from hiveflow import AbortExecutionException, HITLAction, HITLManager

    hitl = HITLManager()
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, hitl_manager=hitl)

    async def gated_task(deps, view):
        return "should_not_run"

    graph = {
        "gate": {
            "task": gated_task,
            "depends_on": [],
            "hitl": {"action": HITLAction.APPROVAL.value, "prompt": "Approve?"},
        },
    }

    exec_task = asyncio.create_task(orch.execute(graph))
    await asyncio.sleep(0.05)
    pending = await hitl.list_pending_gates()
    await hitl.respond(pending[0].gate_id, approved=False)

    with pytest.raises(AbortExecutionException):
        await exec_task


@pytest.mark.asyncio
async def test_dag_orchestrator_checkpoint_after_node():
    from hiveflow import CheckpointManager, MemoryCheckpointBackend

    cp_mgr = CheckpointManager(MemoryCheckpointBackend())
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, checkpoint_manager=cp_mgr, workflow_id="wf_cp")

    async def step(deps, view):
        return {"value": 42}

    graph = {
        "step1": {
            "task": step,
            "depends_on": [],
            "checkpoint": {"when": "after", "metadata": {"label": "step1"}},
        },
    }

    await orch.execute(graph)
    checkpoints = await cp_mgr.list_checkpoints("wf_cp")
    assert len(checkpoints) == 1
    assert checkpoints[0].state["result"] == {"value": 42}
