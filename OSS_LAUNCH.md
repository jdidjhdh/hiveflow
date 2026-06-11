# HiveFlow Open Source Launch Checklist

Track progress toward a LangChain-grade public launch. See [Roadmap](docs/roadmap.md) for long-term phases.

## Phase 0 — Trustworthy launch

- [x] Remove internal dev files (`sitecustomize.py`, planning notes in `.gitignore`)
- [ ] Create GitHub org `hiveflow` and public repo
- [ ] Enable GitHub Discussions + Security Advisories
- [ ] Configure secrets: `PYPI_API_TOKEN`, optional `CODECOV_TOKEN`
- [ ] Tag `v0.1.0` and publish `hiveflow` + `hiveflow-agent` to PyPI
- [ ] Enable GitHub Pages (Actions deploy from `docs.yml`)
- [x] API/docs consistency (`packages/core/README.md`, cookbook, nav)
- [x] CI: Playwright with Studio backend on `:8000`
- [x] CI: Vitest unit tests in frontend job
- [ ] Verify `security@hiveflow.dev` or use GitHub Advisories only

**Exit criteria:** `pip install hiveflow` → run `examples/01_hello_hiveflow.py` → docs site live.

## Phase 1 — Professional polish

- [x] Logo + MkDocs theme branding
- [x] README restructure (positioning + dual Quick Start)
- [x] mkdocstrings API reference (core symbols)
- [x] Cookbook: Studio Agent mode, checkpoint recovery
- [x] Migration guide from LangGraph
- [x] `GOVERNANCE.md`, `.github/FUNDING.yml`
- [ ] Demo GIF in README (`docs/assets/demo-orchestrator.gif`)
- [ ] Discord server + invite link in README
- [ ] Public maintainers list (@handles)

**Exit criteria:** New user understands Agent vs Core path in &lt;10 minutes.

## Phase 2 — Ecosystem

- [x] Benchmark script + `docs/benchmarks/`
- [x] LangGraph adapter PoC (`hiveflow.adapters.langgraph`)
- [x] Case study: [regulated HITL content review](docs/case-studies/regulated-hitl-content-review.md)
- [ ] Optional custom domain `docs.hiveflow.dev`
- [ ] Demo GIF + Discord (optional polish)

## Maintainer actions (cannot automate)

1. **PyPI:** Reserve names, add `PYPI_API_TOKEN` to repo secrets, push tag `v0.1.0`.
2. **GitHub Pages:** Settings → Pages → Source: GitHub Actions.
3. **Discussions:** Settings → General → Features → Discussions.
4. **Codecov:** Connect repo at codecov.io for badge.

## Verification commands

```bash
# Core
cd packages/core && pip install -e ".[dev]" && pytest

# Studio backend
cd packages/studio/backend && pip install -r requirements.txt -r requirements-dev.txt
HIVEFLOW_AGENT_ECHO_LLM=true pytest tests/ -q

# Frontend
cd packages/studio/frontend && npm ci && npm run lint && npm run build && npm run test:unit

# Examples
python examples/run_smoke_tests.py

# Benchmarks
pip install -e packages/core
python benchmarks/run_orchestration_latency.py --quick

# Docs
pip install mkdocs-material "mkdocstrings[python]" && pip install -e packages/core
python -m mkdocs build --strict
```
