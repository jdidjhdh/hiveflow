import pytest
import asyncio
from graphlib import TopologicalSorter
from hiveflow import DAGOrchestrator
from hiveflow.blackboard import SecureBlackboard, MemoryBlackboard


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
