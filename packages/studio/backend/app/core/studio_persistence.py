"""Persistent JSON storage for Studio in-memory settings."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("HIVEFLOW_STUDIO_DATA_DIR", Path(__file__).resolve().parent.parent.parent / "data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _path(name: str) -> Path:
    return _DATA_DIR / name


def load_json(name: str, default: Any) -> Any:
    path = _path(name)
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return default


def save_json(name: str, data: Any) -> None:
    path = _path(name)
    tmp = path.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Failed to save %s: %s", path, exc)
