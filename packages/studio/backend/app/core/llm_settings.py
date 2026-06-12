"""In-memory LLM provider and Agent runtime routing settings for Studio."""
from __future__ import annotations

import os
import time
import uuid
from copy import deepcopy
from typing import Any, Optional

from app.core.studio_persistence import load_json, save_json

_STORE_FILE = "llm_settings.json"
_providers_store: dict[str, dict] = {}

_agent_settings: dict[str, Any] = {
    "use_echo_llm": None,
    "planning_provider_id": None,
    "execution_provider_id": None,
    "updated_at": None,
}


def load_llm_settings() -> None:
    global _providers_store, _agent_settings
    raw = load_json(_STORE_FILE, {"providers": [], "agent": {}})
    _providers_store = {p["id"]: p for p in raw.get("providers", []) if p.get("id")}
    agent = raw.get("agent") or {}
    _agent_settings.update({
        "use_echo_llm": agent.get("use_echo_llm"),
        "planning_provider_id": agent.get("planning_provider_id"),
        "execution_provider_id": agent.get("execution_provider_id"),
        "updated_at": agent.get("updated_at"),
    })


def persist_llm_settings() -> None:
    save_json(_STORE_FILE, {
        "providers": list(_providers_store.values()),
        "agent": get_agent_settings_raw(),
    })


def _now() -> float:
    return time.time()


def list_providers() -> list[dict]:
    return [deepcopy(p) for p in _providers_store.values()]


def get_provider(provider_id: str) -> Optional[dict]:
    item = _providers_store.get(provider_id)
    return deepcopy(item) if item else None


def create_provider(data: dict) -> dict:
    provider_id = data.get("id") or f"llm_{uuid.uuid4().hex[:8]}"
    record = {
        "id": provider_id,
        "name": data["name"],
        "provider": data["provider"],
        "model_name": data["model_name"],
        "api_key_credential_id": data.get("api_key_credential_id"),
        "base_url": data.get("base_url"),
        "temperature": float(data.get("temperature", 0.7)),
        "max_tokens": int(data.get("max_tokens", 4096)),
        "top_p": float(data.get("top_p", 1.0)),
        "created_at": _now(),
        "updated_at": _now(),
    }
    _providers_store[provider_id] = record
    persist_llm_settings()
    return deepcopy(record)


def update_provider(provider_id: str, updates: dict) -> Optional[dict]:
    if provider_id not in _providers_store:
        return None
    record = _providers_store[provider_id]
    for key in (
        "name",
        "provider",
        "model_name",
        "api_key_credential_id",
        "base_url",
        "temperature",
        "max_tokens",
        "top_p",
    ):
        if key in updates and updates[key] is not None:
            record[key] = updates[key]
    record["updated_at"] = _now()
    persist_llm_settings()
    return deepcopy(record)


def delete_provider(provider_id: str) -> bool:
    if provider_id not in _providers_store:
        return False
    del _providers_store[provider_id]
    agent = _agent_settings
    if agent.get("planning_provider_id") == provider_id:
        agent["planning_provider_id"] = None
    if agent.get("execution_provider_id") == provider_id:
        agent["execution_provider_id"] = None
    persist_llm_settings()
    return True


def get_agent_settings_raw() -> dict:
    return deepcopy(_agent_settings)


def update_agent_settings(updates: dict) -> dict:
    if "use_echo_llm" in updates:
        _agent_settings["use_echo_llm"] = updates["use_echo_llm"]
    if "planning_provider_id" in updates:
        _agent_settings["planning_provider_id"] = updates["planning_provider_id"]
    if "execution_provider_id" in updates:
        _agent_settings["execution_provider_id"] = updates["execution_provider_id"]
    _agent_settings["updated_at"] = _now()
    persist_llm_settings()
    return deepcopy(_agent_settings)


def reset_llm_settings_store() -> None:
    _providers_store.clear()
    _agent_settings.clear()
    _agent_settings.update({
        "use_echo_llm": None,
        "planning_provider_id": None,
        "execution_provider_id": None,
        "updated_at": None,
    })
    persist_llm_settings()


def resolve_llm_source() -> str:
    agent = _agent_settings
    if agent.get("use_echo_llm") is True:
        return "echo"
    plan_id = agent.get("planning_provider_id")
    exec_id = agent.get("execution_provider_id")
    if agent.get("use_echo_llm") is False and (plan_id or exec_id):
        return "settings"
    if plan_id or exec_id:
        return "settings"
    if os.environ.get("HIVEFLOW_AGENT_ECHO_LLM", "").lower() == "true":
        return "echo"
    return "env"


def get_agent_settings_view(agent_active: bool = False) -> dict:
    agent = deepcopy(_agent_settings)
    source = resolve_llm_source()
    plan = get_provider(agent.get("planning_provider_id") or "") if agent.get("planning_provider_id") else None
    exec_p = get_provider(agent.get("execution_provider_id") or "") if agent.get("execution_provider_id") else None
    effective_echo = source == "echo"
    return {
        **agent,
        "llm_source": source,
        "use_echo_llm": effective_echo if agent.get("use_echo_llm") is None else bool(agent.get("use_echo_llm")),
        "agent_active": agent_active,
        "planning_provider": _public_provider(plan),
        "execution_provider": _public_provider(exec_p),
    }


def _public_provider(provider: Optional[dict]) -> Optional[dict]:
    if not provider:
        return None
    return {
        "id": provider["id"],
        "name": provider["name"],
        "provider": provider["provider"],
        "model_name": provider["model_name"],
    }
