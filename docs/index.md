# HiveFlow Documentation

<p align="center">
  <img src="assets/logo.svg" alt="HiveFlow" width="72"/>
</p>

**HiveFlow** is an open-source multi-agent orchestration engine with **Human-in-the-Loop**, a visual **Studio**, and first-class **MCP** tool integration.

> **Status: 0.1.x Alpha** — API may evolve; see [Versioning](versioning.md).

## Choose your path

| I want to… | Start here |
|------------|------------|
| Embed orchestration in Python | [Getting Started](getting-started.md) |
| NL planning + Agent runtime | [Getting Started — Studio Agent](getting-started.md#studio-agent-mode) |
| Visual workflows + ops UI | [Studio Agent Operations](studio-agent-ops.md) |
| Migrate from LangGraph | [Migration guide](guides/migrate-from-langgraph.md) |

## Quick Links

- [Getting Started](getting-started.md) — install and first workflow
- [Core Concepts](concepts.md) — ECM, Cell, Blackboard, Scheduler
- [Cookbook](cookbook/index.md) — HITL, RAG, Studio Agent mode
- [API Reference](api/index.md) — auto-generated core API
- [Architecture](architecture.md) — three-layer design
- [Deployment](deployment.md) — Docker, Kubernetes
- [Observability](observability.md) — metrics, tracing, Studio analytics

## Minimal Example (Core)

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM

async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()
    try:
        async def handler(ecm, view):
            await view.put("result", f"Done: {ecm.intent}")
        await hf.create_agent("worker", {"process"}, set(), {"result"}, handler)
        await hf.scheduler.schedule(ECM(
            trace_id="1", intent="Hello", intent_id="1",
            emitter="user", required_skills=["process"],
        ))
    finally:
        await hf.shutdown()

asyncio.run(main())
```

## Community

- [GitHub Repository](https://github.com/hiveflow/hiveflow)
- [Issue Tracker](https://github.com/hiveflow/hiveflow/issues)
- [Discussions](https://github.com/hiveflow/hiveflow/discussions) (enable in repo settings)
- [Contributing](https://github.com/hiveflow/hiveflow/blob/main/CONTRIBUTING.md)
- [Governance](https://github.com/hiveflow/hiveflow/blob/main/GOVERNANCE.md)
