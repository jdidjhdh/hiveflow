"""HiveFlow - CognitiveOrchestrator tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import LLMClient, LLMMessage, LLMResponse, MockLLMClient
from hiveflow.cognitive_orchestrator import (
    CognitiveOrchestrator, Plan, ExecutionResult, ResultCache
)
import json


# ========== ResultCache Tests ==========

def test_cache_put_and_get():
    cache = ResultCache(max_size=10)
    cache.put("key1", {"value": 42})
    assert cache.get("key1") == {"value": 42}


def test_cache_miss():
    cache = ResultCache()
    assert cache.get("nonexistent") is None


def test_cache_lru_eviction():
    cache = ResultCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)  # Should evict "a"

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_cache_lru_refresh():
    cache = ResultCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")  # Refresh "a" (move to end)
    cache.put("c", 3)  # Should evict "b" (least recently used)

    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_cache_size():
    cache = ResultCache(max_size=5)
    for i in range(3):
        cache.put(f"k{i}", i)
    assert cache.size() == 3


def test_cache_clear():
    cache = ResultCache()
    cache.put("k1", 1)
    cache.put("k2", 2)
    cache.clear()
    assert cache.size() == 0
    assert cache.get("k1") is None


def test_cache_key_generation():
    cache = ResultCache()
    key1 = cache.make_cache_key("research", {"query": "AI trends"})
    key2 = cache.make_cache_key("research", {"query": "AI trends"})
    key3 = cache.make_cache_key("research", {"query": "ML trends"})

    assert key1 == key2
    assert key1 != key3


def test_cache_update_existing():
    cache = ResultCache(max_size=5)
    cache.put("key", 1)
    cache.put("key", 2)  # Update existing
    assert cache.size() == 1
    assert cache.get("key") == 2


# ========== CognitiveOrchestrator Tests ==========

PLAN_RESPONSE = json.dumps({
    "plan": [
        {"step": 1, "action": "Research AI trends", "skill": "research", "depends_on": []},
        {"step": 2, "action": "Summarize findings", "skill": "summarize", "depends_on": [1]},
        {"step": 3, "action": "Review summary", "skill": "review", "depends_on": [2]},
    ],
    "rationale": "Research first, then summarize, then review",
    "estimated_steps": 3,
    "critical_path": [1, 2, 3],
})


@pytest.mark.asyncio
async def test_cognitive_orchestrator_plan():
    """Should generate a plan from goal."""
    client = MockLLMClient(response=PLAN_RESPONSE)
    orchestrator = CognitiveOrchestrator(client)

    plan = await orchestrator.plan("Research AI trends")

    assert len(plan.steps) == 3
    assert plan.steps[0]["skill"] == "research"
    assert plan.steps[1]["depends_on"] == [1]
    assert plan.estimated_steps == 3
    assert plan.critical_path == [1, 2, 3]


@pytest.mark.asyncio
async def test_cognitive_orchestrator_plan_fallback():
    """Should return fallback plan on JSON parse failure."""
    client = MockLLMClient(response="not json at all")
    orchestrator = CognitiveOrchestrator(client)

    plan = await orchestrator.plan("Do something")

    assert len(plan.steps) == 1
    assert plan.steps[0]["action"] == "Do something"
    assert "failed" in plan.rationale.lower()


@pytest.mark.asyncio
async def test_cognitive_orchestrator_execute_success():
    """Should execute plan successfully."""
    client = MockLLMClient(response=PLAN_RESPONSE)
    orchestrator = CognitiveOrchestrator(client)

    executed_steps = []

    async def task_fn(skill, inputs):
        executed_steps.append({"skill": skill, **inputs})
        return {"status": "ok", "skill": skill}

    result = await orchestrator.execute("Research AI trends", task_fn)

    assert result.status == "completed"
    assert len(result.results) == 3
    assert result.replan_count == 0
    assert result.total_latency_ms >= 0
    assert len(result.reasoning_log) > 0


@pytest.mark.asyncio
async def test_cognitive_orchestrator_execute_with_cache():
    """Should use cached results for repeated steps."""
    client = MockLLMClient(response=PLAN_RESPONSE)
    orchestrator = CognitiveOrchestrator(client)

    call_count = {"research": 0, "summarize": 0}

    async def task_fn(skill, inputs):
        call_count[skill] = call_count.get(skill, 0) + 1
        return {"status": "ok"}

    # First execution
    await orchestrator.execute("Research AI trends", task_fn)

    # Second execution with same goal
    await orchestrator.execute("Research AI trends", task_fn)

    # Should have used cache on second run (no additional calls for cached steps)
    assert call_count["research"] == 1  # Only called once (cache on 2nd)
    assert call_count["summarize"] == 1


@pytest.mark.asyncio
async def test_cognitive_orchestrator_replan_on_failure():
    """Should replan when a step fails."""
    plan_response = json.dumps({
        "plan": [
            {"step": 1, "action": "Step 1", "skill": "research", "depends_on": []},
            {"step": 2, "action": "Step 2", "skill": "summarize", "depends_on": [1]},
        ],
        "rationale": "Initial plan",
        "estimated_steps": 2,
        "critical_path": [1, 2],
    })

    replan_response = json.dumps({
        "revised_plan": [
            {"step": 1, "action": "Step 1 (retry)", "skill": "research", "depends_on": []},
            {"step": 2, "action": "Step 2", "skill": "summarize", "depends_on": [1]},
        ],
        "rationale": "Revised after failure",
        "changes": ["Retried step 1"],
    })

    call_count = [0]

    class ReplanningClient(LLMClient):
        async def chat(self, messages, model="", temperature=0.0, max_tokens=4096, tools=None, stop=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return LLMResponse(content=plan_response)
            return LLMResponse(content=replan_response)

    client = ReplanningClient()
    orchestrator = CognitiveOrchestrator(client, max_replans=2)

    step_calls = []

    async def task_fn(skill, inputs):
        step_calls.append(inputs)
        if inputs["step"] == 1 and len([s for s in step_calls if s["step"] == 1]) == 1:
            raise ValueError("Step 1 failed")
        return {"status": "ok"}

    result = await orchestrator.execute("Test goal", task_fn)

    assert result.status == "completed"
    assert result.replan_count >= 1


@pytest.mark.asyncio
async def test_cognitive_orchestrator_max_replans_exceeded():
    """Should fail after max replans."""
    plan_response = json.dumps({
        "plan": [{"step": 1, "action": "Fail", "skill": "test", "depends_on": []}],
        "rationale": "Plan",
    })

    replan_response = json.dumps({
        "revised_plan": [{"step": 1, "action": "Retry", "skill": "test", "depends_on": []}],
        "rationale": "Replan",
    })

    class FailingClient(LLMClient):
        def __init__(self):
            self.calls = 0

        async def chat(self, messages, model="", temperature=0.0, max_tokens=4096, tools=None, stop=None):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(content=plan_response)
            return LLMResponse(content=replan_response)

    client = FailingClient()
    orchestrator = CognitiveOrchestrator(client, max_replans=1)

    async def always_fail(skill, inputs):
        raise ValueError("Always fails")

    result = await orchestrator.execute("Test", always_fail)

    assert result.status == "failed"
    assert result.replan_count == 1


@pytest.mark.asyncio
async def test_cognitive_orchestrator_execute_task_graph():
    """Should return TaskGraph from execution."""
    client = MockLLMClient(response=PLAN_RESPONSE)
    orchestrator = CognitiveOrchestrator(client)

    async def task_fn(skill, inputs):
        return {"status": "ok", "skill": skill}

    graph = await orchestrator.execute_task_graph("Research AI", task_fn)

    assert "step_1" in graph
    assert "step_2" in graph
    assert "step_3" in graph
    assert graph["step_2"]["depends_on"] == ["step_1"]
    assert graph["step_3"]["depends_on"] == ["step_2"]


@pytest.mark.asyncio
async def test_cognitive_orchestrator_reasoning_log():
    """Should maintain reasoning log."""
    client = MockLLMClient(response=PLAN_RESPONSE)
    orchestrator = CognitiveOrchestrator(client)

    async def task_fn(skill, inputs):
        return {"status": "ok"}

    await orchestrator.execute("Test goal", task_fn)

    log = orchestrator.get_reasoning_log()
    assert len(log) > 0
    assert any("Plan generated" in entry for entry in log)
    assert any("completed" in entry for entry in log)


def test_cognitive_orchestrator_clear_cache():
    """Should clear cache and reasoning log."""
    client = MockLLMClient(response=PLAN_RESPONSE)
    orchestrator = CognitiveOrchestrator(client)
    orchestrator.cache.put("key", "value")
    orchestrator._reasoning_log.append("test")

    orchestrator.clear_cache()

    assert orchestrator.cache.size() == 0
    assert len(orchestrator._reasoning_log) == 0


# ========== Plan and ExecutionResult Tests ==========

def test_plan_defaults():
    plan = Plan(steps=[{"step": 1}])
    assert plan.rationale == ""
    assert plan.estimated_steps == 0
    assert plan.critical_path == []
    assert plan.created_at > 0


def test_execution_result_defaults():
    result = ExecutionResult(
        plan=Plan(steps=[]),
        results={},
        status="completed",
    )
    assert result.replan_count == 0
    assert result.total_latency_ms == 0.0
    assert result.reasoning_log == []
