"""
HiveFlow - 01: Hello HiveFlow

This example demonstrates the basic setup and execution of a simple workflow.

Usage:
    python 01_hello_hiveflow.py
"""
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM


async def main():
    # 1. Create the engine
    config = HiveFlowConfig()
    hf = HiveFlow(config)

    # 2. Start the engine
    await hf.start()

    try:
        # 3. Define a simple agent handler
        async def greet_handler(ecm, view):
            """Simple greeting handler."""
            message = f"Hello from {ecm.emitter}! Task: {ecm.intent}"
            await view.put("greeting_result", message)
            return {"message": message}

        # 4. Create an agent
        agent = await hf.create_agent(
            agent_id="greeter",
            skills={"greet", "respond"},
            read_keys=set(),
            write_keys={"greeting_result"},
            task_handler=greet_handler,
        )

        # 5. Schedule a task
        ecm = ECM(
            trace_id="hello-1",
            intent="Say hello to the world",
            intent_id="intent-1",
            emitter="user",
            required_skills=["greet"],
            payload={"message": "Hello"},
        )

        success = await hf.scheduler.schedule(ecm)
        print(f"Task scheduled: {success}")

        # 6. Wait for result
        await asyncio.sleep(0.5)
        result = await hf.blackboard.sys_get("greeting_result")

        print("\nWorkflow completed!")
        print(f"Result: {result}")

    finally:
        # 7. Clean shutdown
        await hf.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
