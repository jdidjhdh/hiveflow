<p align="center">
  <a href="README.md">English</a> · <a href="README.zh.md">简体中文</a>
</p>

<p align="center">
  <img src="docs/assets/logo.svg" alt="HiveFlow" width="80"/>
</p>

<h1 align="center">HiveFlow</h1>

<p align="center">
  <strong>Multi-agent coordination &amp; HITL layer — visual Studio and MCP tools.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/hiveflow-core/"><img src="https://img.shields.io/pypi/v/hiveflow-core.svg" alt="PyPI"/></a>
  <a href="https://pypi.org/project/hiveflow-core/"><img src="https://img.shields.io/pypi/pyversions/hiveflow-core.svg" alt="Python"/></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT"/></a>
  <a href="https://github.com/jdidjhdh/hiveflow/actions/workflows/test.yml"><img src="https://github.com/jdidjhdh/hiveflow/actions/workflows/test.yml/badge.svg" alt="Tests"/></a>
  <a href="https://jdidjhdh.github.io/hiveflow/en/"><img src="https://img.shields.io/badge/docs-English-blue" alt="Docs EN"/></a>
  <a href="https://jdidjhdh.github.io/hiveflow/zh/"><img src="https://img.shields.io/badge/docs-中文-blue" alt="Docs ZH"/></a>
</p>

> **0.1.x Alpha** — [v0.1.0 release](https://github.com/jdidjhdh/hiveflow/releases/tag/v0.1.0) · [versioning policy](docs/en/versioning.md) · [docs](https://jdidjhdh.github.io/hiveflow/)

HiveFlow is the **multi-agent coordination and HITL layer** for teams that need human approval, audited shared state, and a self-hosted ops UI — while staying compatible with runtimes like LangGraph via the [sidecar pattern](docs/en/cookbook/langgraph-sidecar.md).

### Why HiveFlow?

| Differentiator | What you get |
|----------------|--------------|
| **Coordination layer** | Scheduler, blackboard, HITL — use native runtime or [LangGraph sidecar](docs/en/cookbook/langgraph-sidecar.md) |
| **Human-in-the-Loop** | Plan and action gates with Studio Approvals + timeout policies |
| **Visual Studio** | Orchestrator, Chatflow, Analytics, Replay, HITL — self-hosted |
| **Security** | Dual input/output guards + audited, encryptable blackboard |
| **MCP-native** | Unified tool protocol and plugin marketplace hooks |

---

## Golden Path (~5 min)

**Try HiveFlow Studio in Agent mode:** natural language → plan → canvas → execute. No API key required when `HIVEFLOW_AGENT_ECHO_LLM=true` (default in `docker-compose.yml`).

### 1. Docker (recommended)

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
docker compose up --build
```

Open **http://localhost:3000** → **Orchestrator** → enable **Agent / real mode**.

| Step | Action |
|------|--------|
| 1 | Enter a goal (e.g. *Summarize three trends in AI agents*) |
| 2 | Click **Plan only** and review the TaskGraph |
| 3 | **Import to canvas** → **Execute DAG** |

APIs: `POST /api/agent/plan-only` · `execute-plan` · `query` — see [Studio Agent cookbook](docs/en/cookbook/studio-agent-mode.md) ([中文](docs/zh/cookbook/studio-agent-mode.md)).

### 2. PyPI (library / scripts)

```bash
pip install hiveflow-core hiveflow-agent
python examples/01_hello_hiveflow.py
```

Optional extras: `pip install "hiveflow-core[all]"` (security, llm, rag, redis).

### Advanced — embed Core engine only

For low-level control without Studio: register agents, schedule `ECM` tasks, read the blackboard.

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

→ [`examples/01_hello_hiveflow.py`](examples/01_hello_hiveflow.py) · [Core README](packages/core/README.md)

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

Details: [Architecture (EN)](docs/en/architecture.md) · [架构 (ZH)](docs/zh/architecture.md)

---

## Three modules

HiveFlow is a monorepo with three packages. Pick the layer that matches your integration depth.

| Module | Package | Role | Typical user |
|--------|---------|------|--------------|
| **Core** | [`hiveflow`](packages/core/) · PyPI | Orchestration kernel — scheduler, blackboard, DAG/HITL/RAG/MCP | Library authors, backend engineers |
| **Agent** | [`hiveflow-agent`](packages/agent/) · PyPI | NL planning + cognitive Skill graphs on top of Core | Agent builders, LLM app developers |
| **Studio** | [`packages/studio`](packages/studio/) · self-hosted | Visual ops UI + FastAPI backend (REST/WS) | Operators, reviewers, full-stack teams |

### Core — `packages/core` (`hiveflow`)

The **embeddable engine**. You register workers with skills, schedule `ECM` tasks, and coordinate through a shared blackboard. Includes static/dynamic DAG orchestrators, HITL gates, checkpoints, dual guards, RAG, MCP plugin hooks, and Prometheus-friendly metrics — with no UI dependency.

- **Install:** `pip install hiveflow-core` · **Docs:** [Core README](packages/core/README.md) · [API](docs/en/api/index.md)
- **Examples:** `examples/01_hello_hiveflow.py` … `15_multimodal_pipeline.py`

### Agent — `packages/agent` (`hiveflow-agent`)

The **cognitive runtime** on Core. `HiveMindApp` turns natural language into a TaskGraph, binds Skills to ReAct workers, and executes via `CognitiveOrchestrator`. Supports plan-only, full `run_query`, and `execute_plan` on an existing graph — with optional plan HITL before execution.

- **Install:** `pip install hiveflow-agent` · **Docs:** [Agent README](packages/agent/README.md) · [Studio Agent cookbook](docs/en/cookbook/studio-agent-mode.md)
- **Key APIs:** `run_query` · `plan_only` · `execute_plan` (also exposed as `/api/agent/*` in Studio)

### Studio — `packages/studio` (FastAPI + React)

The **visual operations platform**. Orchestrator and Chatflow for workflow design; Approvals for HITL; Analytics, Tracer, and Replay for observability. The backend bridges Core DAG execution and Agent mode (`HIVEFLOW_RUNTIME=agent`), including LangGraph plan export.

- **Run locally:** `docker compose up` or backend `uvicorn` + frontend `npm run dev`
- **Production images:** tagged GHCR images on `v*` releases — see [`docker-compose.release.yml`](docker-compose.release.yml)
- **Feature maturity:** [CAPABILITIES.md](packages/studio/CAPABILITIES.md) (Stable / Beta / Preview / Demo per page)
- **Docs:** [Studio README](packages/studio/README.md) · [Agent ops guide](docs/en/studio-agent-ops.md)

> **v0.1.x preview:** Studio has no built-in login. Deploy behind VPN or a reverse proxy. Electron desktop scripts are **experimental** and not part of release artifacts.

---

## Documentation

| Resource | English | 中文 |
|----------|---------|------|
| Documentation site | [en/](https://jdidjhdh.github.io/hiveflow/en/) | [zh/](https://jdidjhdh.github.io/hiveflow/zh/) |
| Getting Started | [docs/en/getting-started.md](docs/en/getting-started.md) | [docs/zh/getting-started.md](docs/zh/getting-started.md) |
| Three modules | [Core](packages/core/README.md) · [Agent](packages/agent/README.md) · [Studio](packages/studio/README.md) | [Core](packages/core/README.zh.md) · [Agent](packages/agent/README.zh.md) · [Studio](packages/studio/README.zh.md) |
| Cookbook | [docs/en/cookbook/](docs/en/cookbook/) | [docs/zh/cookbook/](docs/zh/cookbook/) |
| OSS launch | [OSS_LAUNCH.md](OSS_LAUNCH.md) | [docs/zh/oss-launch.md](docs/zh/oss-launch.md) |

---

## Project structure

```
HiveFlow/
├── packages/core/          # PyPI: hiveflow — orchestration kernel
├── packages/agent/         # PyPI: hiveflow-agent — NL cognitive runtime
├── packages/studio/        # Self-hosted UI + FastAPI backend
├── examples/               # 16 smoke-tested examples
└── docs/                   # MkDocs（en/ + zh/）
```

See [Three modules](#three-modules) above for what each layer does and when to use it.

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
pip install mkdocs-material "mkdocstrings[python]" mkdocs-static-i18n && pip install -e packages/core
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
