"""Build Agent LLM clients from Studio provider settings."""
from __future__ import annotations

from typing import Any, Optional

from app.api.credentials import get_decrypted_credential
from llm.base import LLMClient


class _ConfiguredLLMClient(LLMClient):
    """Wrap a concrete LLM client with default generation params from Studio settings."""

    def __init__(self, inner: LLMClient, defaults: dict[str, Any]):
        self._inner = inner
        self._defaults = defaults

    def _merge_kwargs(self, kwargs: dict) -> dict:
        merged = dict(self._defaults)
        merged.update(kwargs)
        return merged

    async def complete(self, messages, **kwargs):
        return await self._inner.complete(messages, **self._merge_kwargs(kwargs))

    async def stream(self, messages, **kwargs):
        async for chunk in self._inner.stream(messages, **self._merge_kwargs(kwargs)):
            yield chunk

    async def embed(self, texts):
        return await self._inner.embed(texts)


def create_llm_from_provider(provider: dict) -> LLMClient:
    provider_type = (provider.get("provider") or "openai").lower()
    model = provider.get("model_name")
    api_key = get_decrypted_credential(provider.get("api_key_credential_id") or "")
    base_url = provider.get("base_url") or None

    if provider_type == "openai":
        from llm.openai_client import OpenAILLMClient
        inner = OpenAILLMClient(model=model or "gpt-4o", api_key=api_key, base_url=base_url)
    elif provider_type == "anthropic":
        from llm.anthropic_client import AnthropicLLMClient
        inner = AnthropicLLMClient(model=model or "claude-3-5-sonnet-20241022", api_key=api_key)
    elif provider_type == "deepseek":
        from llm.deepseek_client import DeepSeekLLMClient
        inner = DeepSeekLLMClient(model=model or "deepseek-chat", api_key=api_key, base_url=base_url)
    elif provider_type == "ollama":
        from llm.ollama_client import OllamaLLMClient
        inner = OllamaLLMClient(model=model or "llama3", base_url=base_url)
    elif provider_type == "custom":
        from llm.openai_client import OpenAILLMClient
        if not base_url:
            raise ValueError("Custom provider requires base_url")
        inner = OpenAILLMClient(model=model or "gpt-4o-mini", api_key=api_key, base_url=base_url)
    else:
        raise ValueError(f"Unsupported LLM provider type: {provider_type}")

    defaults = {
        "temperature": provider.get("temperature"),
        "max_tokens": provider.get("max_tokens"),
        "top_p": provider.get("top_p"),
    }
    defaults = {k: v for k, v in defaults.items() if v is not None}
    if defaults:
        return _ConfiguredLLMClient(inner, defaults)
    return inner
