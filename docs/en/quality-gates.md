# Quality Gates (Core · Agent · Studio)

HiveFlow **0.1.x is Alpha** on PyPI (`Development Status :: 3 - Alpha`). APIs may change; see [Versioning](versioning.md).

This page documents **automated gates** and **known gaps** so contributors and adopters share the same expectations.

## Summary

| Package | Tests (local) | Coverage gate | Type check | PyPI / npm |
|---------|---------------|---------------|------------|------------|
| **Core** | 294 pytest | **≥ 60%** (`hiveflow/`) | MyPy on documented public modules | `hiveflow` |
| **Agent** | 162+ pytest (CI) | **≥ 60%** (runtime modules) | — | `hiveflow-agent` (sync version with Core) |
| **Studio backend** | 432 pytest | **≥ 60%** (`app/`) | — | Docker / monorepo only |
| **Studio frontend** | 58 Vitest + 17 Playwright | **≥ 24%** lines (utils/stores); E2E for UI | `tsc --noEmit` | Docker / monorepo only |

Run all local gates:

```bash
python scripts/verify_launch_readiness.py
```

---

## Core

### Alpha classifier

The PyPI trove classifier `Development Status :: 3 - Alpha` is **intentional** for 0.1.x. It signals:

- Semver **0.y.z** — breaking changes may land in minors with CHANGELOG notes
- Not a production SLA from maintainers until **1.0.0** ([Roadmap](roadmap.md))

### MyPy scope

CI runs `mypy` on the **documented public surface** listed in `packages/core/pyproject.toml` under `[tool.mypy] files = [...]`.

- **In scope:** blackboard, bus, scheduler, cell, hitl, checkpoint, orchestrator, app, guards, streaming, validation, plugin_marketplace
- **Not in scope (0.1.x):** RAG internals, multimodal, full `llm_client` — typed incrementally toward 0.2 / 1.0
- Modules with `ignore_errors = true` in overrides are legacy; errors there do not fail CI until cleaned up

Expand coverage by adding paths to `files` and removing overrides when clean.

### Execution backends

Pluggable runtimes for TaskGraph execution (`hiveflow.execution`):

| Backend | Status |
|---------|--------|
| `native` | Production — `DynamicOrchestrator` |
| `langgraph` | Export via `to_langgraph_spec()`; in-process `execute()` stub until v0.3 |

See [LangGraph Sidecar cookbook](cookbook/langgraph-sidecar.md).

---

## Agent

### Coverage gate (CI)

```bash
cd packages/agent
pytest tests/ \
  --ignore=tests/test_real_llm.py \
  --ignore=tests/test_llm_connection.py \
  --cov --cov-fail-under=60
```

Sources: `app`, `core`, `orchestrator`, `worker`, `llm`, `memory`, `guardrails`, `intent_parser`, `protocol`, `replay`, `mcp_skills` (see `pyproject.toml`).

### Real LLM tests (optional, local only)

`tests/test_real_llm.py` and `tests/test_llm_connection.py` are **excluded from CI** because they need a live LLM and outputs are non-deterministic.

```bash
export LLM_PROVIDER=deepseek   # or openai / anthropic / ollama
export DEEPSEEK_API_KEY=...    # provider-specific
cd packages/agent
pytest tests/test_real_llm.py -v -m real_llm
```

Mark: `@pytest.mark.real_llm` — never required for merge.

### Release coupling

`hiveflow-agent` declares `hiveflow>=0.1.0`. **Always publish both packages from the same git tag** (`v0.1.0` → `hiveflow==0.1.0` + `hiveflow-agent==0.1.0`). See [Publishing](publishing.md).

---

## Studio

### Distribution model

Studio is **not** published to PyPI or npm as a standalone product in 0.1.x.

| Artifact | How to consume |
|----------|----------------|
| Full stack | `docker compose up` or `docker-compose.release.yml` |
| Backend only | `packages/studio/backend` + editable `core` + `agent` |
| Frontend only | `packages/studio/frontend` (Vite dev server → API on `:8000`) |

See [Studio README](https://github.com/hiveflow/hiveflow/tree/main/packages/studio#readme) and [Deployment](deployment.md).

### Frontend coverage policy

Vitest thresholds (~**24%** lines) apply to **`src/`** with deliberate excludes:

- `src/pages/**` — covered primarily by **Playwright E2E** (17 scenarios)
- `src/components/orchestrator/hooks/**` — complex React Flow integration; E2E + manual QA

Raising unit coverage for pages is a **0.2.x** goal; do not block Alpha on 80% line coverage for UI shells.

### Demo / preview pages

Not all Studio routes are production-grade. See **[Studio CAPABILITIES.md](https://github.com/hiveflow/hiveflow/blob/main/packages/studio/CAPABILITIES.md)** for the maturity matrix (Stable / Beta / Preview / Demo).

Examples: **A/B testing** = Demo (in-memory only); **Analytics** = Preview.

---

## Related

- [Versioning](versioning.md)
- [Publishing (maintainers)](publishing.md)
- [OSS Launch](oss-launch.md)
