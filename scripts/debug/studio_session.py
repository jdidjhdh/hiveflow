#!/usr/bin/env python3
"""Studio maintainer debug session — backend API smoke + frontend build check."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

DEBUG_DIR = Path(__file__).resolve().parent
ROOT = DEBUG_DIR.parents[1]
BACKEND = ROOT / "packages" / "studio" / "backend"
FRONTEND = ROOT / "packages" / "studio" / "frontend"

sys.path.insert(0, str(DEBUG_DIR))
sys.path.insert(0, str(BACKEND))

from common import log, reset_log


def run_backend_smoke() -> None:
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("HIVEFLOW_DB_TYPE", "sqlite")
    os.environ.setdefault("HIVEFLOW_RATE_LIMIT", "10000")

    from httpx import ASGITransport, AsyncClient

    from app.db.config import close_storage, init_storage
    from app.main import app

    async def _run() -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        os.environ["HIVEFLOW_DB_PATH"] = db_path
        try:
            await init_storage()
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                health = await ac.get("/api/health")
                log(
                    "studio_session:backend",
                    "health check",
                    {
                        "status": health.status_code,
                        "body": health.json() if health.status_code == 200 else health.text[:120],
                    },
                    "H1",
                )

                vars_list = await ac.get("/api/variables")
                create = await ac.post("/api/variables", json={"name": "debug_var", "value": "42"})
                log(
                    "studio_session:backend",
                    "variables API",
                    {"listStatus": vars_list.status_code, "createStatus": create.status_code},
                    "H4",
                )

                wf = await ac.post(
                    "/api/workflows",
                    json={
                        "name": "debug-wf",
                        "description": "studio debug",
                        "nodes": [
                            {
                                "id": "n1",
                                "type": "taskNode",
                                "data": {"label": "A", "task": "a", "variant": "task"},
                            }
                        ],
                        "edges": [],
                    },
                )
                log(
                    "studio_session:backend",
                    "workflow create",
                    {
                        "status": wf.status_code,
                        "hasId": bool(wf.json().get("id") if wf.status_code in (200, 201) else False),
                    },
                    "H2",
                )
        finally:
            await close_storage()
            if os.path.exists(db_path):
                os.unlink(db_path)

    asyncio.run(_run())


def run_frontend_checks() -> None:
    dist = FRONTEND / "dist" / "index.html"
    log(
        "studio_session:frontend",
        "production build artifact",
        {"distExists": dist.exists(), "path": str(dist)},
        "H5",
    )


def main() -> None:
    reset_log()
    log("studio_session:main", "session start", {}, "H0")
    run_backend_smoke()
    run_frontend_checks()
    log("studio_session:main", "session complete", {}, "H0")


if __name__ == "__main__":
    main()
