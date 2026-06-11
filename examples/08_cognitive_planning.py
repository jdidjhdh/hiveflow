"""
HiveFlow - 08: Cognitive Planning

This example demonstrates dynamic planning with the cognitive orchestrator.

Usage:
    python 08_cognitive_planning.py
"""
import asyncio
import json
from hiveflow import CognitiveOrchestrator, MockLLMClient


async def main():
    print("=== Cognitive Planning Example ===\n")

    plan_response = json.dumps({
        "plan": [
            {"step": 1, "action": "Research the topic", "skill": "search", "depends_on": []},
            {"step": 2, "action": "Write the guide", "skill": "write", "depends_on": [1]},
            {"step": 3, "action": "Review the draft", "skill": "review", "depends_on": [2]},
        ],
        "rationale": "Research first, then write, then review",
        "estimated_steps": 3,
        "critical_path": [1, 2, 3],
    })

    llm = MockLLMClient(response=plan_response)
    orchestrator = CognitiveOrchestrator(llm_client=llm)

    async def task_fn(skill: str, inputs: dict):
        return {"skill": skill, "output": f"Completed {skill} for: {inputs.get('goal', '')}"}

    result = await orchestrator.execute(
        goal="Create a comprehensive guide on building scalable AI applications",
        task_fn=task_fn,
    )

    print(f"Status: {result.status}")
    print(f"Plan rationale: {result.plan.rationale}")
    print(f"Steps executed: {len(result.plan.steps)}")
    print(f"Results: {list(result.results.keys())}")
    print(f"Reasoning log: {result.reasoning_log}")


if __name__ == "__main__":
    asyncio.run(main())
