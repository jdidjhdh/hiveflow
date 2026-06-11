"""Local / cloud LLM routing for HiveMind agent runtime."""
import os

from .base import LLMClient
from .provider_factory import create_llm_client


def create_routed_llm_clients(
    planning_provider: str | None = None,
    execution_provider: str | None = None,
    **kwargs,
) -> tuple[LLMClient, LLMClient]:
    """Return (planning_llm, execution_llm).

    Env:
      HIVEFLOW_LLM_PLANNING_PROVIDER — default ollama (local)
      HIVEFLOW_LLM_EXECUTION_PROVIDER — default LLM_PROVIDER or openai
    """
    plan_p = planning_provider or os.environ.get("HIVEFLOW_LLM_PLANNING_PROVIDER", "ollama")
    exec_p = execution_provider or os.environ.get(
        "HIVEFLOW_LLM_EXECUTION_PROVIDER",
        os.environ.get("LLM_PROVIDER", "openai"),
    )
    planning = create_llm_client(plan_p, **kwargs)
    execution = create_llm_client(exec_p, **kwargs)
    return planning, execution
