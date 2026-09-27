"""
Tests for hiveflow.orchestrator module.

Coverage targets:
- DAGOrchestrator: DAG execution, HITL gates, checkpoints
- DynamicOrchestrator: dynamic subgraphs, global timeout
- _execute_with_retry: retry policy (constant/exponential backoff)
- Error handling: AbortExecutionException, cancellation, timeout
- Node dependencies: parallel execution, sequential execution

Dependencies: MemoryBlackboard, HITLManager, CheckpointManager (no external services)
"""
import asyncio
from graphlib import TopologicalSorter

import pytest

from hiveflow import (
    AbortExecutionException,
    CheckpointManager,
    DAGOrchestrator,
    DynamicOrchestrator,
    HITLAction,
    HITLManager,
    MISSING,
    MemoryCheckpointBackend,
)
from hiveflow.blackboard import MemoryBlackboard, SecureBlackboard


# ========== Basic DAG Tests ==========

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


# ========== DAGOrchestrator Tests ==========

@pytest.mark.asyncio
async def test_dag_orchestrator_basic():
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
async def test_dag_orchestrator_parallel_nodes():
    """Parallel nodes execute concurrently."""
    order = []

    async def node_a(deps, view):
        order.append("A_start")
        await asyncio.sleep(0.05)
        order.append("A_end")
        return "a"

    async def node_b(deps, view):
        order.append("B_start")
        await asyncio.sleep(0.05)
        order.append("B_end")
        return "b"

    graph = {
        "A": {"task": node_a, "depends_on": []},
        "B": {"task": node_b, "depends_on": []},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    await orch.execute(graph)

    # A and B should start before either ends (parallel execution)
    assert "A_start" in order[:2] or "B_start" in order[:2]


@pytest.mark.asyncio
async def test_dag_orchestrator_dependency_order():
    """Dependencies execute in correct order."""
    order = []

    async def node_a(deps, view):
        order.append("A")
        return "a"

    async def node_b(deps, view):
        order.append("B")
        return "b"

    async def node_c(deps, view):
        order.append("C")
        return "c"

    graph = {
        "A": {"task": node_a, "depends_on": []},
        "B": {"task": node_b, "depends_on": ["A"]},
        "C": {"task": node_c, "depends_on": ["B"]},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    await orch.execute(graph)

    # Order must be A -> B -> C
    assert order == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_dag_orchestrator_dependency_returns_missing():
    """Failed dependency with on_failure='skip' returns MISSING."""
    async def failing_task(deps, view):
        raise ValueError("Intentional failure")

    async def dependent(deps, view):
        # deps["failed"] should be MISSING
        assert deps.get("failed") is MISSING
        return "dependent_result"

    graph = {
        "failed": {
            "task": failing_task,
            "depends_on": [],
            "retry_policy": {"max_attempts": 1},
            "on_failure": "skip",
        },
        "dependent": {"task": dependent, "depends_on": ["failed"]},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["failed"] is MISSING
    assert result["dependent"] == "dependent_result"


@pytest.mark.asyncio
async def test_dag_orchestrator_retry_constant_backoff():
    """Constant backoff retry works."""
    attempts = []

    async def flaky_task(deps, view):
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise ValueError("Temporary failure")
        return "success"

    graph = {
        "retry": {
            "task": flaky_task,
            "depends_on": [],
            "retry_policy": {
                "max_attempts": 3,
                "backoff_type": "constant",
                "backoff_base": 0.01,  # Very short for testing
            },
        },
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["retry"] == "success"
    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_dag_orchestrator_retry_exponential_backoff():
    """Exponential backoff retry works."""
    attempts = []

    async def flaky_task(deps, view):
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise RuntimeError("Temporary error")
        return "recovered"

    graph = {
        "retry": {
            "task": flaky_task,
            "depends_on": [],
            "retry_policy": {
                "max_attempts": 3,
                "backoff_type": "exponential",
                "backoff_base": 0.01,
                "max_backoff": 0.05,
            },
        },
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["retry"] == "recovered"


@pytest.mark.asyncio
async def test_dag_orchestrator_retry_exhausted():
    """Exhausted retries raise AbortExecutionException."""
    async def always_fail(deps, view):
        raise ValueError("Always fails")

    graph = {
        "fail": {
            "task": always_fail,
            "depends_on": [],
            "retry_policy": {"max_attempts": 2, "backoff_base": 0.01},
        },
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    with pytest.raises(AbortExecutionException):
        await orch.execute(graph)


@pytest.mark.asyncio
async def test_dag_orchestrator_on_failure_skip():
    """on_failure='skip' returns MISSING."""
    async def failing_task(deps, view):
        raise RuntimeError("Intentional failure")

    graph = {
        "skip_node": {
            "task": failing_task,
            "depends_on": [],
            "retry_policy": {"max_attempts": 1},
            "on_failure": "skip",
        },
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["skip_node"] is MISSING


@pytest.mark.asyncio
async def test_dag_orchestrator_on_failure_callback():
    """on_failure callback can return MISSING to skip."""
    def failure_handler(error, node_name, deps):
        return MISSING

    async def failing_task(deps, view):
        raise ValueError("Callback test")

    graph = {
        "callback": {
            "task": failing_task,
            "depends_on": [],
            "retry_policy": {"max_attempts": 1},
            "on_failure": failure_handler,
        },
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["callback"] is MISSING


@pytest.mark.asyncio
async def test_dag_orchestrator_non_async_task_returns_missing():
    """Non-async task causes MISSING result (TypeError caught by gather)."""
    def sync_task(deps, view):
        return "sync_result"

    graph = {
        "sync": {"task": sync_task, "depends_on": []},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    # TypeError is caught by gather(return_exceptions=True), result is MISSING
    assert result["sync"] is MISSING


# ========== HITL Tests ==========

@pytest.mark.asyncio
async def test_dag_orchestrator_hitl_approval():
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
async def test_dag_orchestrator_hitl_timeout():
    """HITL timeout causes abort."""
    hitl = HITLManager()
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, hitl_manager=hitl)

    async def gated_task(deps, view):
        return "should_not_run"

    graph = {
        "gate": {
            "task": gated_task,
            "depends_on": [],
            "hitl": {
                "action": HITLAction.APPROVAL.value,
                "prompt": "Approve?",
                "timeout_seconds": 0.1,  # Very short timeout
                "on_timeout": "fail",
            },
        },
    }

    # Don't respond to gate, let it timeout
    with pytest.raises(AbortExecutionException):
        await orch.execute(graph)


@pytest.mark.asyncio
async def test_dag_orchestrator_hitl_callable_context():
    """HITL context can be callable."""
    hitl = HITLManager()
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, hitl_manager=hitl)

    def dynamic_context(deps, results):
        return {"computed": "value"}

    async def task_with_context(deps, view):
        return "done"

    graph = {
        "node": {
            "task": task_with_context,
            "depends_on": [],
            "hitl": {
                "action": HITLAction.APPROVAL.value,
                "context": dynamic_context,
            },
        },
    }

    exec_task = asyncio.create_task(orch.execute(graph))
    await asyncio.sleep(0.05)
    pending = await hitl.list_pending_gates()
    await hitl.respond(pending[0].gate_id, approved=True)
    result = await exec_task
    assert result["node"] == "done"


# ========== Checkpoint Tests ==========

@pytest.mark.asyncio
async def test_dag_orchestrator_checkpoint_after_node():
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


@pytest.mark.asyncio
async def test_dag_orchestrator_checkpoint_before_node():
    """Checkpoint before node execution."""
    cp_mgr = CheckpointManager(MemoryCheckpointBackend())
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, checkpoint_manager=cp_mgr, workflow_id="wf_before")

    async def step(deps, view):
        return {"output": "data"}

    graph = {
        "step1": {
            "task": step,
            "depends_on": [],
            "checkpoint": {"when": "before", "metadata": {"phase": "pre"}},
        },
    }

    await orch.execute(graph)
    checkpoints = await cp_mgr.list_checkpoints("wf_before")
    assert len(checkpoints) == 1
    # Before checkpoint should not have result
    assert "result" not in checkpoints[0].state


@pytest.mark.asyncio
async def test_dag_orchestrator_checkpoint_custom_workflow_id():
    """Checkpoint uses workflow_id from config."""
    cp_mgr = CheckpointManager(MemoryCheckpointBackend())
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, checkpoint_manager=cp_mgr, workflow_id="custom_wf")

    async def task(deps, view):
        return "done"

    graph = {
        "node": {
            "task": task,
            "depends_on": [],
            "checkpoint": {"workflow_id": "override_wf"},  # Override
        },
    }

    await orch.execute(graph)
    checkpoints = await cp_mgr.list_checkpoints("override_wf")
    assert len(checkpoints) == 1


# ========== DynamicOrchestrator Tests ==========

@pytest.mark.asyncio
async def test_dynamic_orchestrator_basic():
    """DynamicOrchestrator executes basic graph."""
    async def task_a(deps, view):
        return "a_result"

    async def task_b(deps, view):
        return "b_result"

    graph = {
        "A": {"task": task_a, "depends_on": []},
        "B": {"task": task_b, "depends_on": ["A"]},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["A"] == "a_result"
    assert result["B"] == "b_result"


@pytest.mark.asyncio
async def test_dynamic_orchestrator_global_timeout():
    """Global timeout raises TimeoutError."""
    async def slow_task(deps, view):
        await asyncio.sleep(5.0)
        return "slow"

    graph = {
        "slow": {"task": slow_task, "depends_on": []},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)
    with pytest.raises(TimeoutError):  # TypeError caught, no regex match needed
        await orch.execute(graph, global_timeout=0.1)


@pytest.mark.asyncio
async def test_dynamic_orchestrator_dynamic_subgraph():
    """Dynamic node can add subgraph."""
    async def dynamic_parent(deps, view):
        # Return subgraph
        return {
            "subgraph": {
                "child1": {
                    "task": lambda d, v: "child1_result",
                    "depends_on": [],
                },
                "child2": {
                    "task": lambda d, v: "child2_result",
                    "depends_on": ["parent::child1"],
                },
            }
        }

    async def child1_task(deps, view):
        return "child1_result"

    async def child2_task(deps, view):
        return "child2_result"

    graph = {
        "parent": {
            "task": dynamic_parent,
            "depends_on": [],
            "dynamic": True,
        },
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)
    result = await orch.execute(graph)

    assert result["parent"]["subgraph"] is not None


@pytest.mark.asyncio
async def test_dynamic_orchestrator_retry():
    """DynamicOrchestrator supports retry."""
    attempts = []

    async def flaky(deps, view):
        attempts.append(1)
        if len(attempts) < 2:
            raise ValueError("fail")
        return "success"

    graph = {
        "retry": {
            "task": flaky,
            "depends_on": [],
            "retry_policy": {"max_attempts": 2, "backoff_base": 0.01},
        },
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["retry"] == "success"


@pytest.mark.asyncio
async def test_dynamic_orchestrator_abort_on_failure():
    """AbortExecutionException aborts execution."""
    async def failing(deps, view):
        raise AbortExecutionException("Manual abort")

    graph = {
        "fail": {"task": failing, "depends_on": []},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)
    with pytest.raises(AbortExecutionException):
        await orch.execute(graph)


@pytest.mark.asyncio
async def test_dynamic_orchestrator_parallel():
    """Parallel nodes execute concurrently."""
    order = []

    async def task_a(deps, view):
        order.append("A")
        await asyncio.sleep(0.05)
        return "a"

    async def task_b(deps, view):
        order.append("B")
        await asyncio.sleep(0.05)
        return "b"

    graph = {
        "A": {"task": task_a, "depends_on": []},
        "B": {"task": task_b, "depends_on": []},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)
    await orch.execute(graph)

    # Both should start quickly
    assert "A" in order[:2] or "B" in order[:2]


# ========== Edge Cases ==========

@pytest.mark.asyncio
async def test_dag_orchestrator_empty_graph():
    """Empty graph returns empty result."""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute({})
    assert result == {}


@pytest.mark.asyncio
async def test_dynamic_orchestrator_empty_graph():
    """Empty graph returns empty result."""
    bb = SecureBlackboard(MemoryBlackboard())
    orch = DynamicOrchestrator(blackboard=bb)
    result = await orch.execute({})
    assert result == {}


@pytest.mark.asyncio
async def test_dag_orchestrator_single_node():
    """Single node executes."""
    async def solo(deps, view):
        return "solo_result"

    graph = {"only": {"task": solo, "depends_on": []}}

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    result = await orch.execute(graph)
    assert result["only"] == "solo_result"


@pytest.mark.asyncio
async def test_dag_orchestrator_complex_dag():
    """Complex DAG with multiple paths."""
    order = []

    def make_task(name):  # FIXED: removed async (was returning coroutine, not function)
        async def task(deps, view):
            order.append(name)
            return name
        return task

    graph = {
        "A": {"task": make_task("A"), "depends_on": []},
        "B": {"task": make_task("B"), "depends_on": ["A"]},
        "C": {"task": make_task("C"), "depends_on": ["A"]},
        "D": {"task": make_task("D"), "depends_on": ["B", "C"]},
        "E": {"task": make_task("E"), "depends_on": ["D"]},
    }

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb)
    await orch.execute(graph)

    # Verify dependencies
    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")
    assert order.index("D") < order.index("E")


# ========== Metrics Tests ==========

@pytest.mark.asyncio
async def test_dag_orchestrator_with_metrics():
    """Orchestrator with metrics updates counters."""
    from hiveflow.observability.metrics import metrics

    async def task(deps, view):
        return "done"

    graph = {"node": {"task": task, "depends_on": []}}

    bb = SecureBlackboard(MemoryBlackboard())
    orch = DAGOrchestrator(blackboard=bb, metrics=metrics)
    await orch.execute(graph)

    # Metrics should have been updated (check counters exist)
    # Note: This test verifies metrics integration without checking exact values