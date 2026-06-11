"""Tests for LangGraph adapter PoC."""

import pytest

from hiveflow.adapters.langgraph import (
    langgraph_to_taskgraph,
    render_langgraph_python,
    taskgraph_to_langgraph,
)


SAMPLE_PLAN = {
    "research": {"task": "search", "depends_on": []},
    "draft": {"task": "write", "depends_on": ["research"]},
    "review": {
        "task": "review",
        "depends_on": ["draft"],
        "hitl": {"action": "approval", "prompt": "Approve draft?"},
    },
    "final_answer": {"task": "summarize", "depends_on": ["review"]},
}


def test_taskgraph_to_langgraph_structure():
    spec = taskgraph_to_langgraph(SAMPLE_PLAN, workflow_id="demo")
    assert spec["version"] == "0.1-poc"
    assert spec["workflow_id"] == "demo"
    assert spec["entry_point"] == "research"
    assert any(e["from"] == "__start__" for e in spec["edges"])
    assert any(e["to"] == "__end__" for e in spec["edges"])
    assert "review" in spec["interrupt_before"]


def test_roundtrip_preserves_topology():
    spec = taskgraph_to_langgraph(SAMPLE_PLAN)
    plan = langgraph_to_taskgraph(spec)
    assert set(plan.keys()) == set(SAMPLE_PLAN.keys())
    assert plan["draft"]["depends_on"] == ["research"]
    assert plan["review"]["depends_on"] == ["draft"]
    assert plan["research"]["task"] == "search"


def test_render_langgraph_python_contains_nodes():
    spec = taskgraph_to_langgraph(SAMPLE_PLAN)
    code = render_langgraph_python(spec)
    assert "StateGraph" in code
    assert "node_research" in code
    assert "builder.add_edge(START" in code
    assert "END)" in code


def test_unknown_dependency_raises():
    bad = {"a": {"task": "x", "depends_on": ["missing"]}}
    with pytest.raises(ValueError, match="Unknown dependency"):
        taskgraph_to_langgraph(bad)
