# HiveFlow Core

[English](README.md) · **简体中文**

**PyPI：** [`hiveflow`](https://pypi.org/project/hiveflow/) · **路径：** `packages/core`

The embeddable orchestration kernel of HiveFlow. Core provides the primitives to build multi-agent systems in Python without a UI or LLM dependency — you bring task handlers, Core handles scheduling, shared state, and workflow structure.

## What it does

| Area | Components |
|------|------------|
| **Messaging** | `ECM` (Event-Condition-Messaging), in-process or Redis event bus |
| **Workers** | `Cell` supervision tree, skill-based `Scheduler` (least-loaded / auction / load-aware) |
| **Shared state** | `SecureBlackboard` — memory, TTL, Redis, or encrypted backends with audit |
| **Workflows** | `DAGOrchestrator`, `DynamicOrchestrator`, checkpoint / time travel |
| **Safety & compliance** | `HITLManager`, input/output `Guards`, validation pipeline |
| **Data & tools** | RAG pipeline, MCP plugin manager, evaluation / A/B testing |
| **Observability** | Metrics collector, optional OpenTelemetry tracing |

## When to use Core

- Embed orchestration inside your own service or framework
- Need full control over agents, blackboard keys, and scheduler policy
- Build custom HITL or DAG logic without Studio or NL planning
- Ship a minimal dependency (`pip install hiveflow`) without Agent/LLM stack

For natural-language planning and Skill graphs, add [`hiveflow-agent`](../agent/README.md). For a visual ops UI, use [Studio](../studio/README.md).

## Installation

```bash
pip install hiveflow
pip install "hiveflow[security]"   # encryption + JSON schema
pip install "hiveflow[llm]"        # OpenAI + Anthropic clients
pip install "hiveflow[rag]"        # RAG utilities
pip install "hiveflow[all]"        # all optional extras
```

From source:

```bash
cd packages/core && pip install -e ".[dev]"
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

Runnable example: [`examples/01_hello_hiveflow.py`](../../examples/01_hello_hiveflow.py)

## Development

```bash
cd packages/core
pip install -e ".[dev]"
pytest --cov=hiveflow --cov-fail-under=60
ruff check hiveflow/
mypy   # public API surface — see Quality below
```

## Quality (0.1.x Alpha)

| Gate | Target |
|------|--------|
| PyPI classifier | `Development Status :: 3 - Alpha` — intentional for 0.1.x |
| Test coverage | **≥ 60%** on `hiveflow/` (CI enforced) |
| MyPy | Documented public modules in `pyproject.toml` `[tool.mypy] files` |

RAG internals, multimodal, and full `llm_client` typing are **out of scope** for 0.1.x and will expand toward 1.0. Full matrix: [Quality Gates](https://hiveflow.github.io/hiveflow/en/quality-gates/).

## Documentation

- [Getting Started](https://hiveflow.github.io/hiveflow/getting-started/)
- [API Reference](https://hiveflow.github.io/hiveflow/api/)
- [Architecture — Layer 1](https://hiveflow.github.io/hiveflow/architecture/)
- [Main repository README](../../README.md)

## License

MIT — same as the HiveFlow project root.
