# Scripts

| Script | Purpose |
|--------|---------|
| [`verify_launch_readiness.py`](verify_launch_readiness.py) | Phase 0 automated gate (tests, docs, twine) |
| [`pre_release_check.py`](pre_release_check.py) | Pre-push hygiene + readiness (run before first GitHub publish) |
| [`debug/`](debug/) | Maintainer-only local diagnostics |

```bash
python scripts/pre_release_check.py
```
