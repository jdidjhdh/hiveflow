"""
HiveFlow - 04: Checkpoint and Time Travel

This example demonstrates state snapshots and time travel capabilities.

Usage:
    python 04_checkpoint.py
"""
import asyncio
from hiveflow import (
    HiveFlow, HiveFlowConfig, ECM,
    CheckpointManager, MemoryCheckpointBackend,
)


async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()

    checkpoint_mgr = CheckpointManager(MemoryCheckpointBackend())
    workflow_id = "checkpoint-demo-1"

    try:
        print("=== Checkpoint and Time Travel Example ===\n")

        step_counter = {"count": 0}

        async def processor_handler(ecm, view):
            step_counter["count"] += 1
            step_num = step_counter["count"]
            previous_state = await view.get(f"step_{step_num - 1}_state") if step_num > 1 else None
            current_state = {
                "step": step_num,
                "data": f"Processed at step {step_num}",
                "previous": previous_state,
            }
            await view.put(f"step_{step_num}_state", current_state)
            print(f"  Step {step_num} completed")
            return current_state

        await hf.create_agent(
            agent_id="processor",
            skills={"process", "analyze"},
            read_keys={f"step_{i}_state" for i in range(1, 4)},
            write_keys={f"step_{i}_state" for i in range(1, 4)},
            task_handler=processor_handler,
        )

        for i, skill in enumerate(["process", "analyze", "process"], start=1):
            print(f"\nRunning step {i}...")
            await hf.scheduler.schedule(ECM(
                trace_id=workflow_id,
                intent=f"Process data - step {i}",
                intent_id=f"step-{i}",
                emitter="user",
                required_skills=[skill],
            ))
            await asyncio.sleep(0.3)

            state = await hf.blackboard.sys_get(f"step_{i}_state")
            cp_id = await checkpoint_mgr.save_checkpoint(
                workflow_id,
                state=state,
                metadata={"step": i, "description": f"After step {i}"},
            )
            print(f"  Checkpoint saved: {cp_id}")

        checkpoints = await checkpoint_mgr.list_checkpoints(workflow_id)
        print(f"\n{len(checkpoints)} checkpoints available")

        restored = await checkpoint_mgr.restore_checkpoint(checkpoints[1].checkpoint_id)
        print(f"Restored step 2 state: {restored.state['data']}")

        timeline = await checkpoint_mgr.get_checkpoint_timeline(workflow_id)
        print(f"Timeline entries: {len(timeline)}")

    finally:
        await hf.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
