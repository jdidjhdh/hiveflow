# Maintainer debug sessions

Optional local diagnostics **not run in CI**. Logs go to `.debug/maintainer.log` (gitignored).

```bash
# From repo root (install packages/core editable first for core_session)
pip install -e packages/core
python scripts/debug/core_session.py

cd packages/agent && pip install -r requirements.txt
python ../../scripts/debug/agent_session.py

pip install -r packages/studio/backend/requirements.txt
python scripts/debug/studio_session.py
```
