"""
HiveFlow - 01: Hello HiveFlow

This example demonstrates the basic setup and execution of a simple workflow.

Usage:
    python 01_hello_hiveflow.py
"""
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, HiveFlow


async def main():
    # 1. Create the engine with mock LLM (no API key needed)
    config = HiveFlowConfig(llm_provider="mock")
    hf = HiveFlow(config)

    # 2. Start the engine
    await hf.start()

    try:
        # 3. Execute a simple workflow
        result = await hf.execute_workflow(
            agents=[
                {"id": "agent-1", "skills": {"greet", "respond"}},
            ],
            task="Say hello to the world"
        )

        print("Workflow completed!")
        print(f"Result: {result}")

    finally:
        # 4. Clean shutdown
        await hf.stop()


if __name__ == "__main__":
    asyncio.run(main())
