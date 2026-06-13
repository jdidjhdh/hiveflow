# Scripts

| Script | Purpose |
|--------|---------|
| [`verify_launch_readiness.py`](verify_launch_readiness.py) | Phase 0 automated gate (tests, docs, twine) |
| [`pre_release_check.py`](pre_release_check.py) | Pre-push hygiene + readiness (run before first GitHub publish) |
| [`setup_github_repo.py`](setup_github_repo.py) | One-click GitHub setup (Discussions, topics, security, release sync) |
| [`setup_github_repo.ps1`](setup_github_repo.ps1) | Windows wrapper (uses git credential manager) |
| [`debug/`](debug/) | Maintainer-only local diagnostics |

```bash
python scripts/pre_release_check.py
```
