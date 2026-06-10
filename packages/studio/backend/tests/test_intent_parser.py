"""HiveFlow - IntentParser tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import IntentParser, MockLLMClient, ParsedIntent
import json


# ========== Mock responses ==========

PIPELINE_RESPONSE = json.dumps({
    "intent_type": "pipeline",
    "description": "Research and summarize a topic",
    "nodes": [
        {"id": "research", "type": "task", "skill": "research", "label": "Research"},
        {"id": "summarize", "type": "task", "skill": "summarize", "label": "Summarize"},
        {"id": "review", "type": "task", "skill": "review", "label": "Review"},
    ],
    "edges": [
        {"source": "research", "target": "summarize"},
        {"source": "summarize", "target": "review"},
    ],
    "confidence": 0.95,
})


@pytest.mark.asyncio
async def test_parse_pipeline_intent():
    """Should parse a pipeline intent correctly."""
    client = MockLLMClient(response=PIPELINE_RESPONSE)
    parser = IntentParser(client)

    result = await parser.parse("Research a topic, summarize findings, and review the summary")

    assert result.intent_type == "pipeline"
    assert result.confidence == 0.95
    assert len(result.nodes) == 3
    assert result.nodes[0]["skill"] == "research"
    assert result.nodes[1]["skill"] == "summarize"
    assert result.nodes[2]["skill"] == "review"
    assert len(result.edges) == 2


@pytest.mark.asyncio
async def test_parse_conditional_intent():
    """Should parse a conditional workflow."""
    conditional_response = json.dumps({
        "intent_type": "conditional",
        "description": "Check condition and branch",
        "nodes": [
            {"id": "check", "type": "condition", "label": "Check Status"},
            {"id": "approved", "type": "task", "skill": "write", "label": "Approved Path"},
            {"id": "rejected", "type": "task", "skill": "notify", "label": "Rejected Path"},
        ],
        "edges": [
            {"source": "check", "target": "approved", "label": "yes"},
            {"source": "check", "target": "rejected", "label": "no"},
        ],
        "confidence": 0.85,
    })
    client = MockLLMClient(response=conditional_response)
    parser = IntentParser(client)

    result = await parser.parse("Check if the request is approved, if yes write a response, else notify")

    assert result.intent_type == "conditional"
    assert result.confidence == 0.85
    assert result.nodes[0]["type"] == "condition"


@pytest.mark.asyncio
async def test_parse_unknown_intent():
    """Should handle unclear intents."""
    unknown_response = json.dumps({
        "intent_type": "unknown",
        "description": "Unclear request",
        "nodes": [],
        "edges": [],
        "confidence": 0.2,
    })
    client = MockLLMClient(response=unknown_response)
    parser = IntentParser(client)

    result = await parser.parse("Do something cool")

    assert result.intent_type == "unknown"
    assert result.confidence == 0.2


@pytest.mark.asyncio
async def test_parse_handles_json_error():
    """Should handle invalid JSON responses gracefully."""
    client = MockLLMClient(response="This is not JSON at all!!!")
    parser = IntentParser(client)

    result = await parser.parse("Create a workflow")

    assert result.intent_type == "unknown"
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_to_task_graph_pipeline():
    """Should convert a pipeline ParsedIntent to TaskGraph."""
    client = MockLLMClient(response=PIPELINE_RESPONSE)
    parser = IntentParser(client)

    parsed = await parser.parse("Research, summarize, and review")
    graph = parser.to_task_graph(parsed)

    assert graph is not None
    assert "research" in graph
    assert "summarize" in graph
    assert "review" in graph

    # Check dependencies
    assert graph["research"]["depends_on"] == []
    assert graph["summarize"]["depends_on"] == ["research"]
    assert graph["review"]["depends_on"] == ["summarize"]


@pytest.mark.asyncio
async def test_to_task_graph_returns_none_for_unknown():
    """Should return None for unknown intents."""
    client = MockLLMClient(response=json.dumps({
        "intent_type": "unknown",
        "description": "Unclear",
        "nodes": [],
        "edges": [],
        "confidence": 0.1,
    }))
    parser = IntentParser(client)

    parsed = await parser.parse("Do something")
    graph = parser.to_task_graph(parsed)

    assert graph is None


@pytest.mark.asyncio
async def test_to_task_graph_conditional():
    """Should convert conditional ParsedIntent to TaskGraph."""
    conditional_response = json.dumps({
        "intent_type": "conditional",
        "description": "Conditional workflow",
        "nodes": [
            {"id": "check", "type": "condition", "label": "Check"},
            {"id": "pass", "type": "task", "skill": "write", "label": "Pass"},
            {"id": "fail", "type": "task", "skill": "notify", "label": "Fail"},
        ],
        "edges": [
            {"source": "check", "target": "pass", "label": "yes"},
            {"source": "check", "target": "fail", "label": "no"},
        ],
        "confidence": 0.8,
    })
    client = MockLLMClient(response=conditional_response)
    parser = IntentParser(client)

    parsed = await parser.parse("Check and branch")
    graph = parser.to_task_graph(parsed)

    assert graph is not None
    assert graph["pass"]["depends_on"] == ["check"]
    assert graph["fail"]["depends_on"] == ["check"]


@pytest.mark.asyncio
async def test_intent_parser_custom_skills():
    """Should include available skills in system prompt."""
    client = MockLLMClient(response=PIPELINE_RESPONSE)
    parser = IntentParser(
        client,
        available_skills=["code_review", "test_generation", "debug"],
    )
    assert "code_review" in parser.system_prompt
    assert "test_generation" in parser.system_prompt
    assert "debug" in parser.system_prompt


@pytest.mark.asyncio
async def test_intent_parser_records_metadata():
    """Should record LLM call metadata in result."""
    client = MockLLMClient(response=PIPELINE_RESPONSE)
    parser = IntentParser(client, model="gpt-4o")

    result = await parser.parse("Test workflow")

    assert result.metadata["model"] == "gpt-4o"
    assert "latency_ms" in result.metadata


@pytest.mark.asyncio
async def test_to_task_graph_edge_cases():
    """Should handle edges that reference non-existent nodes gracefully."""
    bad_edges_response = json.dumps({
        "intent_type": "pipeline",
        "description": "Bad edges",
        "nodes": [
            {"id": "node_a", "type": "task", "skill": "research", "label": "A"},
        ],
        "edges": [
            {"source": "nonexistent", "target": "node_a"},
        ],
        "confidence": 0.5,
    })
    client = MockLLMClient(response=bad_edges_response)
    parser = IntentParser(client)

    parsed = await parser.parse("Bad edges")
    graph = parser.to_task_graph(parsed)

    # The edge should be ignored since nonexistent node doesn't exist
    assert graph is not None
    assert graph["node_a"]["depends_on"] == []
