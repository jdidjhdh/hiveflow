"""Resolve planning/execution LLM clients for Studio Agent runtime."""
from __future__ import annotations

import logging
import os

from app.core.echo_llm import create_echo_llm
from app.core.llm_client_factory import create_llm_from_provider
from app.core.llm_settings import get_agent_settings_raw, get_provider, resolve_llm_source

logger = logging.getLogger(__name__)


def resolve_llm_clients():
    source = resolve_llm_source()
    if source == "echo":
        echo = create_echo_llm()
        return echo, echo, "echo"

    agent = get_agent_settings_raw()
    if source == "settings":
        plan_id = agent.get("planning_provider_id")
        exec_id = agent.get("execution_provider_id")
        plan_provider = get_provider(plan_id) if plan_id else None
        exec_provider = get_provider(exec_id) if exec_id else None
        fallback = plan_provider or exec_provider
        if fallback:
            try:
                planning = create_llm_from_provider(plan_provider or fallback)
                execution = create_llm_from_provider(exec_provider or fallback)
                return planning, execution, "settings"
            except Exception as exc:
                logger.warning("Studio LLM settings unavailable (%s), falling back", exc)

    try:
        from llm.routing import create_routed_llm_clients
        planning, execution = create_routed_llm_clients()
        return planning, execution, "env"
    except Exception as exc:
        logger.warning("Env LLM routing unavailable (%s), using echo LLM", exc)
        echo = create_echo_llm()
        return echo, echo, "echo"
