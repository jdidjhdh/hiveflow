"""Studio LLM provider and Agent runtime configuration API."""
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.engine_service import get_engine
from app.core.llm_settings import (
    create_provider,
    delete_provider,
    get_agent_settings_view,
    get_provider,
    list_providers,
    update_agent_settings,
    update_provider,
)

router = APIRouter(prefix="/llm", tags=["llm"])


class LLMProviderRequest(BaseModel):
    id: Optional[str] = None
    name: str
    provider: Literal["openai", "anthropic", "ollama", "deepseek", "custom"]
    model_name: str
    api_key_credential_id: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(4096, ge=1, le=128000)
    top_p: float = Field(1.0, ge=0, le=1)


class LLMProviderUpdateRequest(BaseModel):
    name: Optional[str] = None
    provider: Optional[Literal["openai", "anthropic", "ollama", "deepseek", "custom"]] = None
    model_name: Optional[str] = None
    api_key_credential_id: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1, le=128000)
    top_p: Optional[float] = Field(None, ge=0, le=1)


class AgentLLMSettingsRequest(BaseModel):
    use_echo_llm: Optional[bool] = None
    planning_provider_id: Optional[str] = None
    execution_provider_id: Optional[str] = None
    reload_agent: bool = True


@router.get("/providers")
async def get_llm_providers():
    return {"providers": list_providers()}


@router.post("/providers")
async def add_llm_provider(body: LLMProviderRequest):
    if body.api_key_credential_id:
        from app.api.credentials import get_decrypted_credential
        if get_decrypted_credential(body.api_key_credential_id) is None:
            raise HTTPException(status_code=400, detail="Credential not found")
    provider = create_provider(body.model_dump())
    return provider


@router.put("/providers/{provider_id}")
async def edit_llm_provider(provider_id: str, body: LLMProviderUpdateRequest):
    if body.api_key_credential_id:
        from app.api.credentials import get_decrypted_credential
        if get_decrypted_credential(body.api_key_credential_id) is None:
            raise HTTPException(status_code=400, detail="Credential not found")
    provider = update_provider(provider_id, body.model_dump(exclude_unset=True))
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.delete("/providers/{provider_id}")
async def remove_llm_provider(provider_id: str):
    if not delete_provider(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"deleted": True}


@router.post("/providers/test")
async def test_llm_provider(body: LLMProviderRequest):
    from app.core.llm_client_factory import create_llm_from_provider
    try:
        client = create_llm_from_provider(body.model_dump())
        await client.complete(
            [{"role": "user", "content": "ping"}],
            max_tokens=8,
        )
        return {"success": True, "message": "连接成功"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@router.get("/agent")
async def get_agent_llm_settings():
    engine = get_engine()
    return get_agent_settings_view(agent_active=engine._hive_mind is not None)


@router.put("/agent")
async def update_agent_llm_settings(body: AgentLLMSettingsRequest):
    engine = get_engine()
    updates = body.model_dump(exclude={"reload_agent"}, exclude_unset=True)
    for pid_key in ("planning_provider_id", "execution_provider_id"):
        pid = updates.get(pid_key)
        if pid and get_provider(pid) is None:
            raise HTTPException(status_code=400, detail=f"Provider not found: {pid}")

    if body.use_echo_llm is False and not body.planning_provider_id and not body.execution_provider_id:
        raw = get_agent_settings_view()
        if not raw.get("planning_provider_id") and not raw.get("execution_provider_id"):
            raise HTTPException(
                status_code=400,
                detail="Select at least one provider when disabling Echo LLM",
            )

    update_agent_settings(updates)
    reloaded = False
    reload_error = None
    if body.reload_agent and engine.runtime_mode == "agent" and engine._running:
        try:
            await engine.reload_agent_runtime()
            reloaded = True
        except Exception as exc:
            reload_error = str(exc)

    view = get_agent_settings_view(agent_active=engine._hive_mind is not None)
    return {**view, "reloaded": reloaded, "reload_error": reload_error}
