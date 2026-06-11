"""Tests for hiveflow.cognitive_orchestrator module."""
import json

import pytest

from hiveflow import LLMResponse
from hiveflow.cognitive_orchestrator import (
    CognitiveOrchestrator,
    ExecutionResult,
    ResultCache,
)


class SequentialMockLLM:
    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self._index = 0

    async def chat(self, messages, model="", temperature=0.2, max_tokens=2048, tools=None, stop=None):
        if self._index >= len(self._responses):
            return LLMResponse(content="{}", model="mock", latency_ms=1.0)
        response = self._responses[self._index]
        self._index += 1
        return response


PLAN_JSON = json.dumps({
    "plan": [
        {"step": 1, "action": "research", "skill": "research", "depends_on": []},
        {"step": 2, "action": "summarize", "skill": "write", "depends_on": [1]},
    ],
    "rationale": "Two-step plan",
    "estimated_steps": 2,
    "critical_path": [1, 2],
})

REPLAN_JSON = json.dumps({
    "revised_plan": [
        {"step": 1, "action": "retry", "skill": "general", "depends_on": []},
    ],
    "rationale": "Simplified after failure",
    "changes": ["drop failing step"],
})


class TestResultCache:
    def test_put_get_and_lru(self):
        cache = ResultCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.size() == 2

    def test_make_cache_key_stable(self):
        cache = ResultCache()
        k1 = cache.make_cache_key("skill", {"step": 1, "action": "x"})
        k2 = cache.make_cache_key("skill", {"action": "x", "step": 1})
        assert k1 == k2

    def test_clear(self):
        cache = ResultCache()
        cache.put("x", 1)
        cache.clear()
        assert cache.size() == 0


@pytest.mark.asyncio
async def test_plan_parses_json():
    client = SequentialMockLLM([LLMResponse(content=PLAN_JSON, model="mock", latency_ms=1.0)])
    orch = CognitiveOrchestrator(llm_client=client)

    plan = await orch.plan("Research AI trends")

    assert len(plan.steps) == 2
    assert plan.rationale == "Two-step plan"
    assert plan.estimated_steps == 2


@pytest.mark.asyncio
async def test_plan_fallback_on_invalid_json():
    client = SequentialMockLLM([LLMResponse(content="not json", model="mock", latency_ms=1.0)])
    orch = CognitiveOrchestrator(llm_client=client)

    plan = await orch.plan("Do something")

    assert len(plan.steps) == 1
    assert "fallback" in plan.rationale.lower()


@pytest.mark.asyncio
async def test_execute_completes_all_steps():
    client = SequentialMockLLM([LLMResponse(content=PLAN_JSON, model="mock", latency_ms=1.0)])
    orch = CognitiveOrchestrator(llm_client=client)

    async def task_fn(skill, inputs):
        return {"skill": skill, "inputs": inputs}

    result = await orch.execute("Complete goal", task_fn)

    assert isinstance(result, ExecutionResult)
    assert result.status == "completed"
    assert result.results["step_1"]["skill"] == "research"
    assert result.results["step_2"]["skill"] == "write"
    assert result.replan_count == 0
    assert len(result.reasoning_log) >= 2


@pytest.mark.asyncio
async def test_execute_uses_cache_on_repeat():
    client = SequentialMockLLM([LLMResponse(content=PLAN_JSON, model="mock", latency_ms=1.0)])
    orch = CognitiveOrchestrator(llm_client=client)
    calls = []

    async def task_fn(skill, inputs):
        calls.append(skill)
        return f"done-{skill}"

    await orch.execute("Goal", task_fn)
    await orch.execute("Goal", task_fn)

    assert calls.count("research") == 1
    assert calls.count("write") == 1


@pytest.mark.asyncio
async def test_execute_replans_after_failure():
    client = SequentialMockLLM([
        LLMResponse(content=PLAN_JSON, model="mock", latency_ms=1.0),
        LLMResponse(content=REPLAN_JSON, model="mock", latency_ms=1.0),
    ])
    orch = CognitiveOrchestrator(llm_client=client, max_replans=1)

    async def task_fn(skill, inputs):
        if skill == "write":
            raise RuntimeError("writer unavailable")
        return "ok"

    result = await orch.execute("Goal with failure", task_fn)

    assert result.replan_count == 1
    assert result.status == "completed"
    assert result.results["step_1"] == "ok"


@pytest.mark.asyncio
async def test_execute_task_graph():
    client = SequentialMockLLM([LLMResponse(content=PLAN_JSON, model="mock", latency_ms=1.0)])
    orch = CognitiveOrchestrator(llm_client=client)

    async def task_fn(skill, inputs):
        return {"skill": skill}

    graph = await orch.execute_task_graph("Build graph", task_fn)

    assert "step_1" in graph
    assert "step_2" in graph
    assert graph["step_2"]["depends_on"] == ["step_1"]


@pytest.mark.asyncio
async def test_clear_cache_and_reasoning_log():
    client = SequentialMockLLM([LLMResponse(content=PLAN_JSON, model="mock", latency_ms=1.0)])
    orch = CognitiveOrchestrator(llm_client=client)

    async def task_fn(skill, inputs):
        return "x"

    await orch.execute("Goal", task_fn)
    assert len(orch.get_reasoning_log()) > 0

    orch.clear_cache()
    assert orch.cache.size() == 0
    assert orch.get_reasoning_log() == []
