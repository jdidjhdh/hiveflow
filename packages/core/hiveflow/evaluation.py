"""HiveFlow - Agent Evaluation Framework

Provides tools for evaluating agent performance, output quality, and workflow correctness.
Supports:
- Criteria-based evaluation (accuracy, completeness, safety)
- LLM-as-judge evaluation
- Benchmark suites
- A/B testing between agent configurations
"""

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

try:
    from . import LLMClient, LLMMessage
except ImportError:
    from hiveflow import LLMClient, LLMMessage

logger = logging.getLogger(__name__)


@dataclass
class EvaluationCriteria:
    """A single evaluation criterion."""

    name: str
    description: str
    weight: float = 1.0  # Relative importance
    threshold: float = 0.7  # Minimum acceptable score (0-1)


@dataclass
class EvaluationResult:
    """Result of evaluating a single output."""

    criteria_name: str
    score: float  # 0.0 to 1.0
    reason: str = ""
    passed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    """Complete evaluation report for an agent/workflow."""

    workflow_id: str
    test_name: str
    total_score: float  # Weighted average (0-1)
    passed: bool
    results: list[EvaluationResult] = field(default_factory=list)
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Evaluator:
    """
    Evaluates agent outputs against criteria.

    Usage:
        evaluator = Evaluator()
        evaluator.add_criteria("accuracy", "Is the output factually correct?")
        evaluator.add_criteria("completeness", "Does the output address all requirements?")
        evaluator.add_criteria("safety", "Does the output avoid harmful content?")

        report = await evaluator.evaluate(
            workflow_id="wf_001",
            test_name="report_generation",
            input_text="Generate a market analysis",
            output_text="The market shows...",
            expected_output="A comprehensive market analysis covering...",
        )
    """

    def __init__(self, llm_client: LLMClient | None = None, model: str = ""):
        self.llm_client = llm_client
        self.model = model
        self.criteria: dict[str, EvaluationCriteria] = {}
        self._custom_evaluators: dict[str, Callable] = {}

    def add_criteria(
        self,
        name: str,
        description: str,
        weight: float = 1.0,
        threshold: float = 0.7,
    ):
        """Add an evaluation criterion."""
        self.criteria[name] = EvaluationCriteria(
            name=name,
            description=description,
            weight=weight,
            threshold=threshold,
        )

    def add_custom_evaluator(self, name: str, fn: Callable):
        """Add a custom evaluation function."""
        self._custom_evaluators[name] = fn
        if name not in self.criteria:
            self.criteria[name] = EvaluationCriteria(name=name, description=f"Custom: {name}")

    async def evaluate(
        self,
        workflow_id: str,
        test_name: str,
        input_text: str,
        output_text: str,
        expected_output: str = "",
        context: str = "",
    ) -> EvaluationReport:
        """Evaluate an agent's output against all registered criteria."""
        start = time.monotonic()
        results = []

        for name, criterion in self.criteria.items():
            if name in self._custom_evaluators:
                score, reason = await self._run_custom_evaluator(
                    name, input_text, output_text, expected_output, context
                )
            elif self.llm_client:
                score, reason = await self._run_llm_evaluator(
                    criterion, input_text, output_text, expected_output, context
                )
            else:
                # No evaluator available, skip
                continue

            results.append(
                EvaluationResult(
                    criteria_name=name,
                    score=score,
                    reason=reason,
                    passed=score >= criterion.threshold,
                )
            )

        # Calculate weighted average
        total_weight = sum(self.criteria[r.criteria_name].weight for r in results) if results else 1
        weighted_sum = sum(r.score * self.criteria[r.criteria_name].weight for r in results)
        total_score = weighted_sum / total_weight if total_weight > 0 else 0

        elapsed_ms = (time.monotonic() - start) * 1000

        return EvaluationReport(
            workflow_id=workflow_id,
            test_name=test_name,
            total_score=round(total_score, 4),
            passed=all(r.passed for r in results),
            results=results,
            latency_ms=elapsed_ms,
        )

    async def _run_llm_evaluator(
        self,
        criterion: EvaluationCriteria,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: str,
    ) -> tuple:
        """Use LLM as judge for evaluation."""
        prompt = f"""Evaluate the following agent output against this criterion:

Criterion: {criterion.name}
Description: {criterion.description}

Input: {input_text}
Expected: {expected_output}
Output: {output_text}
Context: {context}

Rate the output on a scale of 0.0 to 1.0 for how well it meets the criterion.
Respond with ONLY a JSON object: {{"score": 0.85, "reason": "brief explanation"}}
"""
        messages = [
            LLMMessage(role="system", content="You are an objective evaluator. Respond with ONLY JSON."),
            LLMMessage(role="user", content=prompt),
        ]
        try:
            response = await self.llm_client.chat(
                messages=messages,
                model=self.model,
                temperature=0.0,
                max_tokens=200,
            )
            import json

            content = response.content.strip()
            if content.startswith("```"):
                content = "\n".join(content.split("\n")[1:-1])
            parsed = json.loads(content)
            score = float(parsed.get("score", 0.5))
            reason = parsed.get("reason", "")
            return max(0.0, min(1.0, score)), reason
        except Exception as e:
            logger.warning(f"LLM evaluation failed for {criterion.name}: {e}")
            return 0.5, f"Evaluation error: {e}"

    async def _run_custom_evaluator(
        self,
        name: str,
        input_text: str,
        output_text: str,
        expected_output: str,
        context: str,
    ) -> tuple:
        """Run a custom evaluation function."""
        fn = self._custom_evaluators[name]
        try:
            result = fn(input_text, output_text, expected_output, context)
            if isinstance(result, tuple):
                return result
            return float(result), ""
        except Exception as e:
            logger.warning(f"Custom evaluator failed for {name}: {e}")
            return 0.5, f"Evaluation error: {e}"


class BenchmarkSuite:
    """
    A suite of test cases for benchmarking agent performance.

    Usage:
        suite = BenchmarkSuite("agent_benchmark_v1")
        suite.add_test(
            name="summarization",
            input="Summarize: The quick brown fox...",
            expected="A short summary of the fox story",
            criteria=["accuracy", "completeness"],
        )

        results = await suite.run(evaluator, agent_fn)
    """

    def __init__(self, name: str):
        self.name = name
        self.tests: list[dict[str, Any]] = []

    def add_test(
        self,
        name: str,
        input_text: str,
        expected_output: str,
        criteria: list[str] | None = None,
        context: str = "",
    ):
        """Add a test case to the benchmark."""
        self.tests.append(
            {
                "name": name,
                "input": input_text,
                "expected": expected_output,
                "criteria": criteria or [],
                "context": context,
            }
        )

    async def run(
        self,
        evaluator: Evaluator,
        agent_fn: Callable[[str], Awaitable[str]],
    ) -> list[EvaluationReport]:
        """Run all tests in the suite."""
        reports = []
        for test in self.tests:
            # Filter criteria if specified
            if test["criteria"]:
                original_criteria = dict(evaluator.criteria)
                evaluator.criteria = {k: v for k, v in original_criteria.items() if k in test["criteria"]}

            output = await agent_fn(test["input"])
            report = await evaluator.evaluate(
                workflow_id="benchmark",
                test_name=f"{self.name}/{test['name']}",
                input_text=test["input"],
                output_text=output,
                expected_output=test["expected"],
                context=test["context"],
            )

            # Restore criteria
            if test["criteria"]:
                evaluator.criteria = original_criteria

            reports.append(report)

        return reports

    def summary(self, reports: list[EvaluationReport]) -> dict[str, Any]:
        """Generate a summary of benchmark results."""
        if not reports:
            return {"tests": 0}
        total_score = sum(r.total_score for r in reports) / len(reports)
        passed = sum(1 for r in reports if r.passed)
        avg_latency = sum(r.latency_ms for r in reports) / len(reports)
        return {
            "suite": self.name,
            "tests": len(reports),
            "passed": passed,
            "failed": len(reports) - passed,
            "pass_rate": round(passed / len(reports), 4),
            "avg_score": round(total_score, 4),
            "avg_latency_ms": round(avg_latency, 2),
        }


class ABTester:
    """
    A/B testing for comparing two agent configurations.

    Usage:
        tester = ABTester(evaluator)
        results = await tester.compare(
            input_text="Summarize this article...",
            agent_a_fn=agent_v1,
            agent_b_fn=agent_v2,
            test_name="summarization_comparison",
        )
    """

    def __init__(self, evaluator: Evaluator):
        self.evaluator = evaluator

    async def compare(
        self,
        input_text: str,
        agent_a_fn: Callable[[str], Awaitable[str]],
        agent_b_fn: Callable[[str], Awaitable[str]],
        test_name: str,
        expected_output: str = "",
        context: str = "",
    ) -> dict[str, EvaluationReport]:
        """Run A/B comparison between two agent configurations."""
        output_a = await agent_a_fn(input_text)
        report_a = await self.evaluator.evaluate(
            workflow_id="ab_a",
            test_name=f"{test_name}/A",
            input_text=input_text,
            output_text=output_a,
            expected_output=expected_output,
            context=context,
        )

        output_b = await agent_b_fn(input_text)
        report_b = await self.evaluator.evaluate(
            workflow_id="ab_b",
            test_name=f"{test_name}/B",
            input_text=input_text,
            output_text=output_b,
            expected_output=expected_output,
            context=context,
        )

        return {
            "A": report_a,
            "B": report_b,
            "winner": "A" if report_a.total_score > report_b.total_score else "B",
            "score_diff": round(report_a.total_score - report_b.total_score, 4),
        }
