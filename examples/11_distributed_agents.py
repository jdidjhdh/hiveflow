"""
HiveFlow - 11: Distributed Agents with Redis

This example demonstrates Redis-backed event bus and blackboard.

Usage:
    python 11_distributed_agents.py

Note: Requires Redis at redis://localhost:6379. Falls back to in-memory if unavailable.
"""
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM


async def run_workflow(hf: HiveFlow, label: str) -> None:
    async def worker_handler(ecm, view):
        result = {"node": label, "processed": ecm.intent}
        await view.put("distributed_result", result)
        return result

    await hf.create_agent(
        agent_id=f"worker-{label}",
        skills={"process"},
        read_keys=set(),
        write_keys={"distributed_result"},
        task_handler=worker_handler,
    )

    await hf.scheduler.schedule(ECM(
        trace_id="distributed-1",
        intent=f"Process on {label}",
        intent_id=f"task-{label}",
        emitter="user",
        required_skills=["process"],
    ))
    await asyncio.sleep(0.5)
    result = await hf.blackboard.sys_get("distributed_result")
    print(f"  [{label}] Result: {result}")


async def main():
    print("=== Distributed Agents Example ===\n")

    redis_config = HiveFlowConfig(
        blackboard_type="redis",
        redis_url="redis://localhost:6379",
    )

    try:
        hf = HiveFlow(redis_config)
        await hf.start()
        print("Connected via Redis backend")
        try:
            await run_workflow(hf, "redis-node")
        finally:
            await hf.shutdown()
    except Exception as exc:
        print(f"Redis unavailable ({exc}). Using in-memory backend.\n")
        hf = HiveFlow(HiveFlowConfig())
        await hf.start()
        try:
            await run_workflow(hf, "memory-node")
        finally:
            await hf.shutdown()

    print("\nFor production: set blackboard_type='redis' and run Redis via docker-compose.")


if __name__ == "__main__":
    asyncio.run(main())
