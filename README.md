<p align="center">
  <img src="docs/assets/logo.svg" alt="HiveFlow" width="80"/>
</p>

<h1 align="center">HiveFlow</h1>

<p align="center">
  <strong>Multi-agent orchestration with Human-in-the-Loop, visual Studio, and MCP tools.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/hiveflow/"><img src="https://img.shields.io/pypi/v/hiveflow.svg" alt="PyPI"/></a>
  <a href="https://pypi.org/project/hiveflow/"><img src="https://img.shields.io/pypi/pyversions/hiveflow.svg" alt="Python"/></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT"/></a>
  <a href="https://github.com/hiveflow/hiveflow/actions/workflows/test.yml"><img src="https://github.com/hiveflow/hiveflow/actions/workflows/test.yml/badge.svg" alt="Tests"/></a>
  <a href="https://hiveflow.github.io/hiveflow/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue" alt="Docs"/></a>
</p>

> **0.1.x Alpha** — See [versioning policy](docs/versioning.md) and [OSS launch checklist](OSS_LAUNCH.md).

HiveFlow helps teams build **multi-agent workflows** with native **human approval**, **encrypted shared state**, and a **visual Studio** for planning and operations — without locking observability or HITL behind a paid tier.

### Why HiveFlow?

| Differentiator | What you get |
|----------------|--------------|
| **Human-in-the-Loop** | Plan and action gates with Studio Approvals + timeout policies |
| **Visual Studio** | Orchestrator, Chatflow, Analytics, Replay, HITL — self-hosted |
| **Security** | Dual input/output guards + audited, encryptable blackboard |
| **MCP-native** | Unified tool protocol and plugin marketplace hooks |

---

## Quick Start

### Install

```bash
pip install hiveflow                  # core engine
pip install hiveflow-agent            # NL planning + cognitive orchestration
pip install "hiveflow[all]"           # optional: security, llm, rag, redis
```

### Path A — Core engine (embedded)

Low-level control: register agents, schedule `ECM` tasks, read the blackboard.

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
            intent="Research AI trends",
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

→ [`examples/01_hello_hiveflow.py`](examples/01_hello_hiveflow.py)

### Path B — Agent runtime (NL orchestration)

High-level cognitive planning via `hiveflow-agent` or Studio:

```bash
export HIVEFLOW_RUNTIME=agent HIVEFLOW_AGENT_ECHO_LLM=true
cd packages/studio/backend && uvicorn app.main:app --port 8000
```

Studio APIs: `POST /api/agent/query` · `plan-only` · `execute-plan` — see [Studio Agent cookbook](docs/cookbook/studio-agent-mode.md).

---

## Features

| Area | Capabilities |
|------|----------------|
| Orchestration | Static/dynamic DAG, cognitive planning, 3 scheduler strategies |
| Collaboration | Event bus, skill-based routing, multi-agent blackboard |
| HITL | Approval gates, plan review, Studio + WebSocket notifications |
| Data | RAG pipeline, checkpoints (time travel), streaming SSE |
| Tools | MCP protocol, plugin marketplace, ReAct workers |
| Ops | Studio UI, Prometheus analytics, trace replay |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HiveFlow Studio (Web UI)                 │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST + WebSocket
┌─────────────────────────────▼───────────────────────────────┐
│                   HiveFlow Agent Runtime                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              HiveFlow Core (scheduler, HITL, RAG, MCP)       │
└─────────────────────────────────────────────────────────────┘
```

Details: [Architecture docs](docs/architecture.md)

---

## Documentation

| Resource | Link |
|----------|------|
| Getting Started | [docs/getting-started.md](docs/getting-started.md) |
| **Documentation site** | [hiveflow.github.io/hiveflow](https://hiveflow.github.io/hiveflow/) |
| Cookbook | [docs/cookbook/](docs/cookbook/) |
| API (auto-generated) | [docs/api/](docs/api/index.md) |
| Migrate from LangGraph | [docs/guides/migrate-from-langgraph.md](docs/guides/migrate-from-langgraph.md) |
| Benchmarks | [docs/benchmarks/orchestration-latency.md](docs/benchmarks/orchestration-latency.md) |
| Studio ops | [docs/studio-agent-ops.md](docs/studio-agent-ops.md) |
| OSS launch checklist | [OSS_LAUNCH.md](OSS_LAUNCH.md) |

---

## Project structure

```
HiveFlow/
├── packages/core/          # PyPI: hiveflow
├── packages/agent/         # PyPI: hiveflow-agent
├── packages/studio/        # FastAPI + React Studio
├── examples/               # 15 smoke-tested examples
└── docs/                   # MkDocs site
```

---

## Development

```bash
# Core tests
cd packages/core && pip install -e ".[dev]" && pytest

# Studio backend
cd packages/studio/backend && pip install -r requirements.txt -r requirements-dev.txt
HIVEFLOW_AGENT_ECHO_LLM=true pytest tests/

# Frontend
cd packages/studio/frontend && npm ci && npm run lint && npm run test:unit && npm run build

# Docs
pip install mkdocs-material "mkdocstrings[python]" && pip install -e packages/core
python -m mkdocs build --strict
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [GOVERNANCE.md](GOVERNANCE.md).

---

## Comparison

| Feature | HiveFlow | LangGraph | CrewAI | AutoGen |
|---------|:--------:|:---------:|:------:|:-------:|
| Dynamic orchestration | ✅ | ⚠️ | ❌ | ⚠️ |
| Human-in-the-Loop | ✅ | ⚠️ | ❌ | ⚠️ |
| Checkpoint / replay | ✅ | ✅ | ❌ | ❌ |
| Security guards | ✅ | ❌ | ❌ | ❌ |
| MCP protocol | ✅ | ❌ | ❌ | ❌ |
| Visual ops UI | ✅ | 💰 | ❌ | ❌ |

*✅ Built-in · ⚠️ Custom · ❌ N/A · 💰 Paid product*

---

## Maintainers

HiveFlow is maintained by the core team. Interested in helping? See [CONTRIBUTING.md](CONTRIBUTING.md).

<!-- Add @handles when the public org is created -->

---

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

Inspired by LangGraph, CrewAI, and AutoGen · Built on [MCP](https://github.com/modelcontextprotocol) · Studio UI uses [Ant Design](https://ant.design/) and [React](https://react.dev/)
