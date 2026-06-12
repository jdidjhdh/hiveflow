"""Shared helpers for maintainer debug sessions (not run in CI)."""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / ".debug" / "maintainer.log"


def reset_log() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")


def log(location: str, message: str, data: dict, hypothesis_id: str = "H0") -> None:
    entry = {
        "location": location,
        "message": message,
        "data": data,
        "hypothesisId": hypothesis_id,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
