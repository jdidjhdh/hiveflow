# HiveFlow Core

The core engine of HiveFlow — a lightweight multi-agent orchestration system.

## Installation

```bash
pip install hiveflow
```

## Quick Start

Register agents with task handlers, schedule work with `ECM` messages, and read results from the shared blackboard:

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM


async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()

    try:
        async def handler(ecm, view):
            await view.put("result", f"Done: {ecm.intent}")
            return {"status": "ok"}

        await hf.create_agent(
            agent_id="worker",
            skills={"process"},
            read_keys=set(),
            write_keys={"result"},
            task_handler=handler,
        )

        await hf.scheduler.schedule(ECM(
            trace_id="demo-1",
            intent="Say hello",
            intent_id="task-1",
            emitter="user",
            required_skills=["process"],
        ))
        await asyncio.sleep(0.5)
        print(await hf.blackboard.sys_get("result"))
    finally:
        await hf.shutdown()


asyncio.run(main())
```

For cognitive planning and NL queries, install [`hiveflow-agent`](https://pypi.org/project/hiveflow-agent/) and see [Getting Started](https://hiveflow.github.io/hiveflow/getting-started/).

For full documentation, see the [main README](../../README.md).
