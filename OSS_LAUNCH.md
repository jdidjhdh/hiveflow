# HiveFlow Open Source Launch Checklist

Track progress toward a LangChain-grade public launch. See [Roadmap](docs/en/roadmap.md) for long-term phases.

## Phase 0 — Days 1–3 (public distribution)

| Day | Task | Owner | Status |
|-----|------|-------|--------|
| 1 | Create GitHub repo and push `main` | Maintainer | ✅ `jdidjhdh/hiveflow` |
| 1 | Enable **Discussions** + **Security Advisories** | Maintainer | ⬜ |
| 1 | Repo Settings → Pages → **GitHub Actions** (uses `docs.yml`) | Maintainer | ⬜ |
| 2 | Add secret `PYPI_API_TOKEN` (PyPI → Account → API tokens) | Maintainer | ⬜ |
| 2 | Reserve PyPI names `hiveflow` + `hiveflow-agent` (or verify availability) | Maintainer | ⬜ |
| 2 | Tag and publish: `git tag v0.1.0 && git push origin v0.1.0` | Maintainer | ⬜ |
| 3 | README Golden Path (Docker → Studio Agent) | Repo | ✅ |
| 3 | `docker compose up --build` as default dev path | Repo | ✅ |
| 3 | 2-person blind test (≤30 min to first plan on canvas) | Team | ⬜ |

**Day 3 exit criteria:** stranger clones repo → `docker compose up` → Studio plan-only → execute, **or** `pip install hiveflow` → `examples/01_hello_hiveflow.py`.

### Local readiness (automated)

Run from repo root:

```bash
python scripts/pre_release_check.py   # hygiene + full gate
# or:
python scripts/verify_launch_readiness.py
```

### Pre-push file hygiene (before first `git push`)

| Check | Command / rule |
|-------|----------------|
| No secrets / `.env` | `pre_release_check.py` light scan |
| No coverage / Playwright reports | `.gitignore` — remove from index if previously tracked |
| No internal planning notes | `OPTIMIZATION_SUMMARY.md` etc. gitignored |
| Maintainer debug scripts | `scripts/debug/` only (logs → `.debug/`) |
| Stage full monorepo snapshot | `git add -A && git status` |

If `playwright-report/` was committed earlier:

```bash
git rm -r --cached packages/studio/frontend/playwright-report
```

Last verified locally (2026-06-11):

| Check | Result |
|-------|--------|
| Core pytest (294) | ✅ |
| Agent pytest (162+, cov ≥60%) | ✅ |
| Studio backend pytest (432, cov ≥60%) | ✅ |
| Examples smoke (16) | ✅ |
| MkDocs `--strict` | ✅ |
| `twine check` hiveflow 0.1.0 | ✅ |
| `twine check` hiveflow-agent 0.1.0 | ✅ |
| Release workflow (`.github/workflows/release.yml`) | ✅ present |

### Quality gates (documented gaps → 0.1.x policy)

See [docs/en/quality-gates.md](docs/en/quality-gates.md) for the full matrix.

| Area | Policy |
|------|--------|
| Core PyPI Alpha classifier | Intentional; semver 0.y.z |
| Core MyPy | Public API modules in `pyproject.toml`; RAG/multimodal deferred |
| Agent CI coverage | **≥ 60%** (real LLM tests local-only, `-m real_llm`) |
| Agent + Core release | Same tag publishes both PyPI packages |
| Studio distribution | Monorepo + Docker (not standalone npm/PyPI) |
| Studio frontend coverage | **≥ 24%** on utils/stores; pages via Playwright E2E |
| Demo pages | Documented in [CAPABILITIES.md](packages/studio/CAPABILITIES.md) |

## Phase 0 — Trustworthy launch (full)

- [x] Remove internal dev files (`sitecustomize.py`, planning notes in `.gitignore`)
- [x] Public repo pushed (`https://github.com/jdidjhdh/hiveflow`)
- [ ] Enable GitHub Discussions + Security Advisories
- [ ] Configure secrets: `PYPI_API_TOKEN`, optional `CODECOV_TOKEN`
- [ ] Tag `v0.1.0` and publish `hiveflow` + `hiveflow-agent` to PyPI
- [ ] Enable GitHub Pages (Actions deploy from `docs.yml`)
- [x] API/docs consistency (`packages/core/README.md`, cookbook, nav)
- [x] CI: Playwright with Studio backend on `:8000`
- [x] CI: Vitest unit tests in frontend job
- [x] README Golden Path (Docker-first Studio Agent)
- [x] Monorepo-aware Studio Dockerfile + `docker compose`
- [ ] Verify `security@hiveflow.dev` or use GitHub Advisories only

**Exit criteria:** `pip install hiveflow` → run `examples/01_hello_hiveflow.py` → docs site live.

## Phase 1 — Professional polish

- [x] Logo + MkDocs theme branding
- [x] README restructure (positioning + Golden Path)
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
- [x] Case study: [regulated HITL content review](docs/en/case-studies/regulated-hitl-content-review.md)
- [ ] Optional custom domain `docs.hiveflow.dev`
- [ ] Demo GIF + Discord (optional polish)

## Maintainer runbook (cannot automate)

### 1. GitHub public repo

```bash
# After creating org hiveflow/hiveflow on GitHub
git remote add origin git@github.com:hiveflow/hiveflow.git   # if needed
git push -u origin main
```

Settings → General → Features → **Discussions** ✓  
Settings → Pages → Build and deployment → Source: **GitHub Actions**

### 2. PyPI publish (via CI on tag)

```bash
# One-time: add PYPI_API_TOKEN to repo Secrets
git tag v0.1.0
git push origin v0.1.0
# release.yml builds, tests, uploads both packages, creates GitHub Release
```

Manual fallback:

```bash
cd packages/core && python -m build && python -m twine upload dist/*
cd packages/agent && pip install -e ../core && python -m build && python -m twine upload dist/*
```

### 3. Verify after publish

```bash
pip install hiveflow==0.1.0 hiveflow-agent==0.1.0
python -c "import hiveflow; print(hiveflow.__version__)"
```

## Verification commands

```bash
# All-in-one
python scripts/verify_launch_readiness.py

# Individual
cd packages/core && pip install -e ".[dev]" && pytest
cd packages/agent && pip install -r requirements.txt pytest-cov
pytest tests/ --ignore=tests/test_real_llm.py --ignore=tests/test_llm_connection.py --cov --cov-fail-under=60
cd packages/studio/backend && pip install -r requirements.txt -r requirements-dev.txt
HIVEFLOW_AGENT_ECHO_LLM=true pytest tests/ --cov=app --cov-fail-under=60 -q
cd packages/studio/frontend && npm ci && npm run lint && npm run test:coverage && npm run build
python examples/run_smoke_tests.py
python -m mkdocs build --strict
```
