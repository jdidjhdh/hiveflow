"""
HiveFlow - 12: Custom Scheduler Strategy

This example demonstrates a custom scheduling strategy.

Usage:
    python 12_custom_scheduler.py
"""
import asyncio
from typing import List
from hiveflow import HiveFlow, HiveFlowConfig, ECM, SelectionStrategy


class SkillWeightedStrategy(SelectionStrategy):
    """Prefer agents with higher-weighted skill matches and lower load."""

    def __init__(self, skill_weights: dict):
        self.skill_weights = skill_weights

    async def select(self, ecm, capabilities, worker_queues) -> List[str]:
        required = set(ecm.required_skills)
        scored: List[tuple[str, float]] = []

        for agent_id, cap in capabilities.items():
            if not (cap.skills & required):
                continue
            if cap.state != "running" or agent_id not in worker_queues:
                continue
            score = sum(self.skill_weights.get(skill, 1.0) for skill in required if skill in cap.skills)
            score -= cap.load * 0.1
            scored.append((agent_id, score))

        if not scored:
            return []
        scored.sort(key=lambda item: item[1], reverse=True)
        return [scored[0][0]]


async def main():
    print("=== Custom Scheduler Strategy Example ===\n")

    hf = HiveFlow(HiveFlowConfig())
    strategy = SkillWeightedStrategy({
        "search": 2.0,
        "analyze": 3.0,
        "write": 1.5,
    })
    await hf.start()
    await hf.set_strategy(strategy)

    assignments: List[str] = []

    def make_handler(agent_id: str):
        async def handler(ecm, view):
            assignments.append(agent_id)
            await view.put("last_agent", agent_id)
            return {"agent": agent_id}
        return handler

    try:
        for agent_id, skills in [
            ("specialist", {"search", "analyze"}),
            ("generalist", {"search", "write", "analyze"}),
        ]:
            await hf.create_agent(
                agent_id=agent_id,
                skills=skills,
                read_keys=set(),
                write_keys={"last_agent"},
                task_handler=make_handler(agent_id),
            )

        await hf.scheduler.schedule(ECM(
            trace_id="scheduler-demo",
            intent="Analyze research data",
            intent_id="task-1",
            emitter="user",
            required_skills=["analyze"],
        ))
        await asyncio.sleep(0.5)

        winner = await hf.blackboard.sys_get("last_agent")
        print(f"Selected agent: {winner}")
        print(f"Assignment order: {assignments}")

    finally:
        await hf.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
