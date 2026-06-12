# HiveFlow Studio

[English](README.md) · **简体中文**

**路径：** `packages/studio` · **未发布 PyPI** · **技术栈：** FastAPI（后端）+ React / TypeScript（前端）

The self-hosted visual operations platform for HiveFlow. Studio lets teams design workflows on a canvas, switch between Core DAG and Agent runtime, approve plans and actions (HITL), and inspect runs via analytics, tracing, and replay — without a proprietary cloud tier.

## What it does

| Area | Pages / features |
|------|------------------|
| **Design** | Orchestrator (ReactFlow DAG), Chatflow (conversational flows), templates, import/export (`.hflow`) |
| **Agent mode** | NL `run_query`, `plan-only`, canvas `execute-plan`, LangGraph export |
| **HITL** | Approvals (plan + node gates), WebSocket `hitl.pending` notifications |
| **Observability** | Dashboard, Analytics (Prometheus), Tracer, Replay (`intent_id` / audit) |
| **Platform** | Blackboard viewer, variables, plugins/MCP market, knowledge base, checkpoints |
| **Runtime bridge** | `EngineService` — Core workflows **or** `HiveMindApp` when `HIVEFLOW_RUNTIME=agent` |

## Architecture

```
packages/studio/
├── backend/          # FastAPI — /api/*, WebSocket /ws
│   └── app/
│       ├── api/      # workflows, agent, hitl, analytics, replay, …
│       └── core/     # EngineService, agent runtime wiring
└── frontend/         # Vite + React + Ant Design + ReactFlow
    └── src/pages/    # Orchestrator, Chatflow, Approvals, …
```

Backend depends on editable installs of [`../core`](../core/README.md) and [`../agent`](../agent/README.md).

## When to use Studio

- Operators and reviewers need a UI (not just Python APIs)
- Plan approval and audit trails for regulated workflows
- Visual debugging: node status, logs, replay by `intent_id`
- Same repo demo: `docker compose up` for full stack

For library-only embedding, use [Core](../core/README.md) or [Agent](../agent/README.md) without Studio.

## Quick Start

### Docker Compose (recommended)

```bash
docker compose up studio frontend
```

Default env: `HIVEFLOW_RUNTIME=agent`, `HIVEFLOW_PLAN_HITL=true`, `HIVEFLOW_AGENT_ECHO_LLM=true`.

### Manual

```bash
# Backend
cd packages/studio/backend
pip install -r requirements.txt
set HIVEFLOW_RUNTIME=agent          # Windows
set HIVEFLOW_AGENT_ECHO_LLM=true
uvicorn app.main:app --reload --port 8000

# Frontend
cd packages/studio/frontend
npm install && npm run dev
```

Open `http://localhost:3000`. Enable **real mode** in the header, then use Orchestrator → Agent drawer or toolbar.

## Agent HTTP API (backend)

| Endpoint | Description |
|----------|-------------|
| `GET/POST /api/agent/runtime` | Core vs Agent mode |
| `POST /api/agent/query` | Full NL query + execute |
| `POST /api/agent/plan-only` | Generate TaskGraph only |
| `POST /api/agent/execute-plan` | Execute canvas / imported plan |
| `POST /api/agent/export-langgraph` | Export plan to LangGraph JSON (+ optional Python stub) |

## Feature maturity

Studio v0.1.x is a **technical preview**. Each page is labeled in the UI (Stable / Beta / Preview / Demo) and documented in **[CAPABILITIES.md](CAPABILITIES.md)**.

| Level | Meaning |
|-------|---------|
| Stable | Core path; mock + real modes |
| Beta | Real mode works; API may change |
| Preview | Prototype or partial persistence |
| Demo | In-memory / local demo data only |

## Production deployment

Use pinned images from GitHub Container Registry (published on version tags):

```bash
export HIVEFLOW_VERSION=0.1.0
export HIVEFLOW_IMAGE_OWNER=your-github-org   # lowercase
docker compose -f docker-compose.release.yml up -d
```

Images: `ghcr.io/<owner>/hiveflow-studio-api:<version>` · `ghcr.io/<owner>/hiveflow-studio-web:<version>`

**Security:** v0.1.x has **no built-in authentication**. See [SECURITY.md](../../SECURITY.md) and [Deployment security](#deployment-security) below.

## Deployment security

- Do not expose port `8000` to the public internet without an auth-aware reverse proxy.
- Change default `POSTGRES_PASSWORD` in `docker-compose.release.yml` for non-local use.
- Treat mock/demo pages (e.g. A/B testing) as non-production — see [CAPABILITIES.md](CAPABILITIES.md).
- **Electron** (`npm run electron:*`) is experimental and not included in v0.1 release artifacts.

## Development

```bash
# Backend tests (≥ 60% coverage gate)
cd packages/studio/backend
HIVEFLOW_AGENT_ECHO_LLM=true pytest tests/ --cov=app --cov-fail-under=60

# Frontend unit tests (~24% line gate on utils/stores; pages excluded — see below)
cd packages/studio/frontend
npm ci && npm run lint && npm run test:coverage && npm run build

# E2E (starts backend + Vite)
npm run test:e2e
```

### Distribution & coverage policy

Studio is **not** published as standalone PyPI/npm packages in 0.1.x — consume via **monorepo** or **Docker** (`docker compose up`, `docker-compose.release.yml`).

Vitest excludes `src/pages/**` and orchestrator hooks; those routes are covered by **17 Playwright E2E** scenarios and labeled in the UI. See **[CAPABILITIES.md](CAPABILITIES.md)** for Stable / Beta / Preview / Demo pages.

Full quality matrix: [Quality Gates](https://jdidjhdh.github.io/hiveflow/en/quality-gates/).

## Documentation

- [Studio Agent operations](https://jdidjhdh.github.io/hiveflow/studio-agent-ops/)
- [Studio Agent cookbook](https://jdidjhdh.github.io/hiveflow/cookbook/studio-agent-mode/)
- [Architecture — Studio layer](https://jdidjhdh.github.io/hiveflow/architecture/)
- [Main repository README](../../README.md)

## License

MIT — same as the HiveFlow project root.
