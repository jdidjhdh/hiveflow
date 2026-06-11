"""Normalize Studio workflow / agent plans for HiveFlow adapters."""

from __future__ import annotations

from typing import Any


def normalize_studio_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Map canvas export fields to cognitive TaskGraph plan shape."""
    normalized: dict[str, Any] = {}
    for name, raw in plan.items():
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        if "hitl_config" in entry and "hitl" not in entry:
            entry["hitl"] = entry.pop("hitl_config")
        task = entry.get("task")
        if not task:
            skills = entry.get("required_skills") or entry.get("skills")
            if isinstance(skills, list) and skills:
                task = skills[0]
            elif isinstance(skills, str):
                task = skills
        if task:
            entry["task"] = task
        elif "task" not in entry:
            entry["task"] = name
        deps = entry.get("depends_on")
        entry["depends_on"] = list(deps) if deps else []
        normalized[name] = entry
    return normalized
