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
| PyPI publish (`hiveflow`, `hiveflow-agent`) | Maintainer — tag `v0.1.0` |
| GitHub Pages documentation site | Maintainer — enable Pages |
| Integration guides (OpenAI, Redis, Postgres) | Done |
| Coverage gate (core ≥ 60%) | Done |
| MyPy on core public API modules | Done |
| Playwright E2E + backend in CI | Done |
| Vitest unit tests in CI | Done |
| Docs/API consistency + mkdocstrings | Done |
| GOVERNANCE + OSS checklist | Done |
| GitHub Discussions | Maintainer action |
| Demo GIF + Discord | Planned |

**Exit criteria:** A new user can `pip install hiveflow-core`, run an example, and read live docs without reading source code.

---

## Phase 2 — Developer experience (Q3 2026)

| Item | Target |
|------|--------|
| Unified high-level API in code paths | v0.2 |
| Cookbook (5 guides) | Done |
| OpenTelemetry | [Observability guide](observability.md) + export hardening v0.2 |
| Agent/Core blackboard unification | v0.2 |
| Semver policy | [Versioning](versioning.md) |

---

## Phase 3 — Ecosystem (Q4 2026 – 2027)

| Item | Target |
|------|--------|
| Integration hub (20+ connectors) | Community + core |
| LangChain / LangGraph adapter | v0.3 — **PoC** [integration](integrations/langgraph.md) |
| Hosted evaluation & trace UI | Studio or separate |
| Production case studies & benchmarks | [Case study](case-studies/regulated-hitl-content-review.md) + [benchmarks](benchmarks/orchestration-latency.md) |
| **v1.0** API freeze | Studio + Core stable 6 months |

---

## How to influence the roadmap

1. Open a Feature Request issue on GitHub
2. Comment on GitHub Discussions (when enabled)
3. Submit a PR with tests and docs

See [ROADMAP.md](https://github.com/jdidjhdh/hiveflow/blob/main/ROADMAP.md) and [OSS launch checklist](oss-launch.md).
