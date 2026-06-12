# HiveFlow Roadmap

Public roadmap for reaching production-ready open source. Timelines are approximate.

## Current status (v0.1.0 Alpha)

- Core orchestration engine with HITL, RAG, MCP, checkpoint, guards
- Agent runtime (`hiveflow-agent`) with ReAct workers
- Studio visual platform (FastAPI + React)
- 800+ automated tests, 15 runnable examples
- CI: Core / Agent / Studio / Examples / Frontend / E2E (with backend)

---

## Phase 1 — Open source launch (Q2 2026)

| Item | Status |
|------|--------|
| PyPI publish (`hiveflow`, `hiveflow-agent`) | **Maintainer** — tag `v0.1.0` + `PYPI_API_TOKEN` |
| GitHub Pages documentation site | **Maintainer** — enable Pages in repo settings |
| Integration guides (OpenAI, Redis, Postgres) | Done |
| Coverage gate (core ≥ 60%) | Done |
| MyPy on core public API modules | Done |
| Playwright E2E + Studio backend in CI | Done |
| Vitest unit tests in CI | Done |
| Docs/API consistency + mkdocstrings | Done |
| GOVERNANCE + OSS launch checklist | Done |
| GitHub Discussions enabled | Maintainer action — template added |
| Demo GIF + Discord | Planned |

**Exit criteria:** A new user can `pip install hiveflow`, run an example, and read live docs without reading source code.

---

## Phase 2 — Developer experience (Q3 2026)

| Item | Target |
|------|--------|
| Unified high-level API (`HiveMindApp.run_query` as documented default) | v0.2 — README Path B documents Studio; code unification v0.2 |
| Cookbook: regulated HITL, multi-agent debate, RAG+MCP, Studio Agent, checkpoint | **Done (5 guides)** |
| OpenTelemetry trace export | v0.2 — [observability.md](docs/observability.md) documents usage |
| Agent layer deduplicated (single `hiveflow` blackboard) | v0.2 |
| Core coverage ≥ 60% | Done |
| Semver policy + migration notes per minor | [versioning.md](docs/versioning.md) |

---

## Phase 3 — Ecosystem (Q4 2026 – 2027)

| Item | Target |
|------|--------|
| Integration hub (20+ connectors) | Community + core |
| LangChain / LangGraph adapter | v0.3 — **PoC:** `hiveflow.adapters.langgraph` + [integration doc](docs/integrations/langgraph.md) |
| Hosted evaluation & trace UI (LangSmith-class) | Studio or separate |
| Production case studies & benchmarks | 1 case study + orchestration benchmarks (more planned) |
| **v1.0** API freeze | When Studio + Core stable 6 months |

---

## Non-goals (for now)

- Replicating LangChain's 100+ integrations breadth
- SaaS-only features behind a paywall
- Breaking API changes without deprecation period after v1.0

---

## How to influence the roadmap

1. Open a [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) issue
2. Comment on [GitHub Discussions](https://github.com/jdidjhdh/hiveflow/discussions) (when enabled)
3. Submit a PR with tests and docs

Priority: **security / data-loss bugs** > **DX / docs** > **new integrations** > **nice-to-have UI**.
