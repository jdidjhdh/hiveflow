"""
HiveFlow - 09: Evaluation Framework

This example demonstrates the evaluation framework and A/B testing.

Usage:
    python 09_evaluation.py
"""
import asyncio
from hiveflow import Evaluator, BenchmarkSuite, ABTester


def keyword_overlap_score(input_text, output_text, expected_output, context):
    if not expected_output:
        return 0.5, "No reference provided"
    expected_words = set(expected_output.lower().split())
    output_words = set(output_text.lower().split())
    overlap = len(expected_words & output_words) / max(len(expected_words), 1)
    return overlap, f"Keyword overlap: {overlap:.2f}"


async def main():
    print("=== Evaluation Framework Example ===\n")

    evaluator = Evaluator()
    for name, desc in [
        ("accuracy", "Is the output factually aligned with the reference?"),
        ("completeness", "Does the output cover the key points?"),
        ("clarity", "Is the output clear and well structured?"),
    ]:
        evaluator.add_criteria(name, desc)
        evaluator.add_custom_evaluator(name, keyword_overlap_score)

    test_input = "Explain quantum computing"
    test_output = "Quantum computing uses qubits and quantum mechanics for computation."
    reference = "Quantum computing leverages quantum mechanics and qubits for parallel computation."

    report = await evaluator.evaluate(
        workflow_id="eval-demo",
        test_name="quantum_explanation",
        input_text=test_input,
        output_text=test_output,
        expected_output=reference,
    )

    print("Evaluation Report:")
    print(f"  Total score: {report.total_score:.2f}")
    print(f"  Passed: {report.passed}")
    for item in report.results:
        print(f"  - {item.criteria_name}: {item.score:.2f} ({item.reason})")

    async def agent_v1(text):
        return "Quantum computing uses qubits."

    async def agent_v2(text):
        return "Quantum computing leverages quantum mechanics and qubits for parallel computation."

    ab_tester = ABTester(evaluator)
    comparison = await ab_tester.compare(
        input_text=test_input,
        agent_a_fn=agent_v1,
        agent_b_fn=agent_v2,
        test_name="quantum_ab",
        expected_output=reference,
    )

    print(f"\nA/B winner: {comparison['winner']} (diff={comparison['score_diff']:.2f})")

    suite = BenchmarkSuite("demo_suite")
    suite.add_test("quantum", test_input, reference)
    reports = await suite.run(evaluator, agent_v2)
    print(f"Benchmark pass rate: {sum(1 for r in reports if r.passed)}/{len(reports)}")


if __name__ == "__main__":
    asyncio.run(main())
