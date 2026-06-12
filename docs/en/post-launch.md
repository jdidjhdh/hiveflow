# Post-launch checklist (after GitHub push)

Repository: **https://github.com/jdidjhdh/hiveflow**

Complete these steps after the first `git push` to `main`. Items marked **(web)** must be done in GitHub Settings; items marked **(local)** can be run from your machine.

---

## Day 1 — Make the repo usable

| # | Task | How |
|---|------|-----|
| 1 | **Verify CI on `main`** **(web)** | [Actions → Test](https://github.com/jdidjhdh/hiveflow/actions/workflows/test.yml) — wait for green on commit `chore: prepare v0.1.0 public release` |
| 2 | **Enable GitHub Pages** **(web)** | Settings → Pages → Source: **GitHub Actions** (not “Deploy from branch”) |
| 3 | **Verify docs deploy** **(web)** | [Actions → Docs](https://github.com/jdidjhdh/hiveflow/actions/workflows/docs.yml) → site at **https://jdidjhdh.github.io/hiveflow/** (EN: `/en/`, ZH: `/zh/`) |
| 4 | **Enable Discussions** **(web)** | Settings → General → Features → **Discussions** ✓ |
| 5 | **Security advisories** **(web)** | Settings → Security → Private vulnerability reporting (optional) |
| 6 | **Repo About** **(web)** | Description + Website URL (docs link above) + Topics: `multi-agent`, `hitl`, `langgraph`, `mcp`, `python` |

**Local sanity check:**

```bash
git clone https://github.com/jdidjhdh/hiveflow.git /tmp/hiveflow-verify
cd /tmp/hiveflow-verify
python scripts/verify_launch_readiness.py
```

---

## Day 2 — PyPI (optional but recommended)

| # | Task | How |
|---|------|-----|
| 1 | Create PyPI account + API token | https://pypi.org/manage/account/token/ (scope: entire account or project) |
| 2 | Add secret **(web)** | Repo → Settings → Secrets → `PYPI_API_TOKEN` |
| 3 | Tag release **(local)** | See commands below |
| 4 | Confirm packages | https://pypi.org/project/hiveflow/ and `hiveflow-agent` |

```bash
cd E:\HiveFlow
git pull
git tag v0.1.0
git push origin v0.1.0
```

This triggers [`.github/workflows/release.yml`](https://github.com/jdidjhdh/hiveflow/blob/main/.github/workflows/release.yml): build, test, PyPI upload, GitHub Release.

**Before tagging:** ensure PyPI names `hiveflow` and `hiveflow-agent` are available (or you own them).

---

## Day 3 — First user path

| # | Task | How |
|---|------|-----|
| 1 | **Golden Path blind test** | Someone new: `docker compose up --build` → Studio → plan-only → execute (≤30 min) |
| 2 | **PyPI path** | `pip install hiveflow` → `python examples/01_hello_hiveflow.py` (after Day 2) |
| 3 | **Close Dependabot noise** **(web)** | Review or close bulk dependency PRs until you want upgrades |
| 4 | **Pin README clone URL** | Already `github.com/jdidjhdh/hiveflow` after URL sync commit |

---

## Ongoing

- **Issues / Discussions** — support channel for Alpha feedback  
- **CHANGELOG.md** — note breaking changes on each release  
- **Tag `v0.1.x`** — keep `hiveflow` + `hiveflow-agent` versions in sync  
- **Studio** — no PyPI; distribute via repo + `docker-compose.release.yml`  

---

## Pages deploy failed?

1. Settings → Pages → Source must be **GitHub Actions**
2. Re-run: [Actions → Docs → Run workflow](https://github.com/jdidjhdh/hiveflow/actions/workflows/docs.yml)
3. If `github-pages` environment shows **“Waiting for review”**, approve the deployment under Environments

---

| Resource | URL |
|----------|-----|
| Repo | https://github.com/jdidjhdh/hiveflow |
| Docs (EN) | https://jdidjhdh.github.io/hiveflow/en/ |
| Docs (ZH) | https://jdidjhdh.github.io/hiveflow/zh/ |
| CI | https://github.com/jdidjhdh/hiveflow/actions |
| Quality gates | [quality-gates.md](quality-gates.md) |
| OSS launch (full) | [OSS_LAUNCH.md](https://github.com/jdidjhdh/hiveflow/blob/main/OSS_LAUNCH.md) |
