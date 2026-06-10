"""HiveFlow - CognitiveOrchestrator

LLM-driven orchestrator that:
1. Generates execution plans from high-level goals
2. Monitors execution and replans on failure
3. Caches results for repeated sub-tasks
4. Provides explainable reasoning for decisions
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from . import LLMClient, LLMMessage, TaskGraph, MISSING
except ImportError:
    from hiveflow import LLMClient, LLMMessage, TaskGraph, MISSING

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = """You are a cognitive workflow planner for a multi-agent system.

Given a goal or task description, generate a step-by-step execution plan.

Output MUST be valid JSON:
{
  "plan": [
    {"step": 1, "action": "describe action", "skill": "skill_name", "depends_on": []},
    {"step": 2, "action": "describe action", "skill": "skill_name", "depends_on": [1]}
  ],
  "rationale": "Why this plan was chosen",
  "estimated_steps": 3,
  "critical_path": [1, 2, 3]
}

Rules:
1. Each step must have a unique number starting from 1
2. depends_on references step numbers (not node IDs)
3. Include a rationale explaining the plan
4. Keep plans concise and actionable
"""

REPLANNER_SYSTEM_PROMPT = """You are a cognitive workflow replanner.

A plan execution encountered a problem. Analyze the situation and generate a revised plan.

Original plan:
{original_plan}

Failed step: {failed_step}
Error: {error}
Completed steps: {completed}

Output MUST be valid JSON:
{{
  "revised_plan": [
    {{"step": 1, "action": "describe action", "skill": "skill_name", "depends_on": []}}
  ],
  "rationale": "Why this revised plan",
  "changes": ["list of changes made"]
}}
"""


@dataclass
class Plan:
    """A generated execution plan."""
    steps: List[Dict[str, Any]]
    rationale: str = ""
    estimated_steps: int = 0
    critical_path: List[int] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class ExecutionResult:
    """Result of plan execution."""
    plan: Plan
    results: Dict[str, Any]
    status: str  # "completed", "replanned", "failed"
    replan_count: int = 0
    total_latency_ms: float = 0.0
    reasoning_log: List[str] = field(default_factory=list)


class ResultCache:
    """LRU cache for sub-task results."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: Dict[str, Any] = {}
        self._order: List[str] = []

    def get(self, key: str) -> Any:
        if key in self._cache:
            self._order.remove(key)
            self._order.append(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: Any):
        if key in self._cache:
            self._order.remove(key)
        elif len(self._cache) >= self.max_size:
            oldest = self._order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._order.append(key)

    def clear(self):
        self._cache.clear()
        self._order.clear()

    def size(self) -> int:
        return len(self._cache)

    def make_cache_key(self, skill: str, inputs: Dict[str, Any]) -> str:
        """Generate a cache key from skill and inputs."""
        sorted_inputs = json.dumps(inputs, sort_keys=True, default=str)
        return f"{skill}:{sorted_inputs}"


class CognitiveOrchestrator:
    """
    LLM-driven cognitive orchestrator with planning, replanning, and caching.

    Usage:
        orchestrator = CognitiveOrchestrator(llm_client=client)
        result = await orchestrator.execute(
            goal="Research and summarize the latest AI trends",
            task_fn=task_handler,  # async function(skill, inputs) -> result
        )
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = "",
        max_replans: int = 3,
        cache_size: int = 100,
        system_prompt: str = "",
    ):
        self.llm_client = llm_client
        self.model = model
        self.max_replans = max_replans
        self.cache = ResultCache(max_size=cache_size)
        self.system_prompt = system_prompt or PLANNER_SYSTEM_PROMPT
        self._reasoning_log: List[str] = []

    async def plan(self, goal: str) -> Plan:
        """Generate a plan for the given goal."""
        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=f"Goal: {goal}"),
        ]

        response = await self.llm_client.chat(
            messages=messages,
            model=self.model,
            temperature=0.2,
            max_tokens=2048,
        )

        try:
            content = response.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

            parsed = json.loads(content)
            plan = Plan(
                steps=parsed.get("plan", []),
                rationale=parsed.get("rationale", ""),
                estimated_steps=parsed.get("estimated_steps", 0),
                critical_path=parsed.get("critical_path", []),
            )
            self._reasoning_log.append(f"Plan generated: {plan.rationale}")
            return plan
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Plan generation failed: {e}")
            # Return a minimal fallback plan
            return Plan(
                steps=[{"step": 1, "action": goal, "skill": "general", "depends_on": []}],
                rationale=f"LLM plan generation failed, using fallback: {e}",
            )

    async def replan(
        self,
        original_plan: Plan,
        failed_step: Dict[str, Any],
        error: str,
        completed: List[int],
    ) -> Plan:
        """Generate a revised plan after a failure."""
        original_plan_str = json.dumps([s for s in original_plan.steps], indent=2)

        messages = [
            LLMMessage(
                role="system",
                content=REPLANNER_SYSTEM_PROMPT.format(
                    original_plan=original_plan_str,
                    failed_step=json.dumps(failed_step),
                    error=error,
                    completed=completed,
                ),
            ),
            LLMMessage(
                role="user",
                content="Generate a revised plan based on the failure context above.",
            ),
        ]

        response = await self.llm_client.chat(
            messages=messages,
            model=self.model,
            temperature=0.2,
            max_tokens=2048,
        )

        try:
            content = response.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

            parsed = json.loads(content)
            plan = Plan(
                steps=parsed.get("revised_plan", []),
                rationale=parsed.get("rationale", ""),
            )
            self._reasoning_log.append(f"Replan: {plan.rationale}")
            return plan
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Replanning failed: {e}")
            return Plan(
                steps=[],
                rationale=f"Replanning failed: {e}",
            )

    async def execute(
        self,
        goal: str,
        task_fn,  # async function(skill: str, inputs: dict) -> result
    ) -> ExecutionResult:
        """
        Execute a goal using cognitive planning.

        Args:
            goal: High-level goal description
            task_fn: async function(skill, inputs) -> result

        Returns:
            ExecutionResult with plan, results, status, and reasoning log
        """
        start_time = time.monotonic()
        self._reasoning_log.clear()

        plan = await self.plan(goal)
        replan_count = 0
        results: Dict[str, Any] = {}
        completed_steps: List[int] = []

        for attempt in range(self.max_replans + 1):
            success = True
            failed_step = None
            failed_error = None

            for step in plan.steps:
                step_num = step["step"]
                skill = step.get("skill", "general")
                action = step.get("action", "")

                # Check cache
                inputs = {"action": action, "step": step_num}
                cache_key = self.cache.make_cache_key(skill, inputs)
                cached = self.cache.get(cache_key)
                if cached is not None:
                    results[f"step_{step_num}"] = cached
                    self._reasoning_log.append(f"Step {step_num} served from cache")
                    completed_steps.append(step_num)
                    continue

                # Execute
                try:
                    result = await task_fn(skill, inputs)
                    results[f"step_{step_num}"] = result
                    self.cache.put(cache_key, result)
                    completed_steps.append(step_num)
                    self._reasoning_log.append(f"Step {step_num} completed: {skill}")
                except Exception as e:
                    success = False
                    failed_step = step
                    failed_error = str(e)
                    self._reasoning_log.append(f"Step {step_num} failed: {e}")
                    break

            if success:
                status = "completed"
                break

            # Replan
            if replan_count < self.max_replans:
                replan_count += 1
                self._reasoning_log.append(f"Replanning (attempt {replan_count})")
                plan = await self.replan(plan, failed_step, failed_error, completed_steps)
                if not plan.steps:
                    status = "failed"
                    break
            else:
                status = "failed"
                break
        else:
            status = "failed"

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return ExecutionResult(
            plan=plan,
            results=results,
            status=status,
            replan_count=replan_count,
            total_latency_ms=elapsed_ms,
            reasoning_log=list(self._reasoning_log),
        )

    async def execute_task_graph(
        self,
        goal: str,
        task_fn,  # async function(skill: str, inputs: dict) -> result
    ) -> TaskGraph:
        """
        Execute a goal and return the results as a TaskGraph.
        """
        result = await self.execute(goal, task_fn)

        graph: TaskGraph = {}
        for step in result.plan.steps:
            step_num = step["step"]
            skill = step.get("skill", "general")
            action = step.get("action", "")
            depends_on = [f"step_{d}" for d in step.get("depends_on", [])]

            async def placeholder_task(deps, blackboard, _action=action, _skill=skill):
                cached = self.cache.get(self.cache.make_cache_key(_skill, {"action": _action}))
                if cached is not None:
                    return cached
                raise ValueError("Task not executed")

            graph[f"step_{step_num}"] = {
                "task": placeholder_task,
                "depends_on": depends_on,
                "skill": skill,
                "action": action,
            }

        return graph

    def get_reasoning_log(self) -> List[str]:
        return list(self._reasoning_log)

    def clear_cache(self):
        self.cache.clear()
        self._reasoning_log.clear()
