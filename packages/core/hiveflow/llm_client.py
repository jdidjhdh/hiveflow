"""HiveFlow - LLM Client Abstraction Layer

Provides a unified interface for multiple LLM backends (OpenAI, Anthropic, etc.).
All cognitive components (IntentParser, ReActWorker, CognitiveOrchestrator)
use this abstraction to remain backend-agnostic.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:
    """A single message in a conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class LLMToolDefinition:
    """A tool/function definition for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    latency_ms: float = 0.0


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[LLMToolDefinition] | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return the response."""
        ...

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[LLMToolDefinition] | None = None,
        stop: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens. Default implementation falls back to non-streaming."""
        response = await self.chat(messages, model, temperature, max_tokens, tools, stop)
        yield response.content


# ========== OpenAI Client ==========

try:
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


class OpenAIClient(LLMClient):
    """OpenAI-compatible LLM client (supports OpenAI API, Azure OpenAI, and compatible proxies)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o-mini",
        api_version: str | None = None,
        azure_deployment: str | None = None,
    ):
        if not _OPENAI_AVAILABLE:
            raise ImportError("openai>=1.0.0 is required for OpenAIClient")

        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")

        if api_version and azure_deployment:
            # Azure OpenAI mode
            azure_endpoint = base_url or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
            self.client = AsyncAzureOpenAI(
                api_key=self.api_key,
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
            )
        else:
            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self.client = AsyncOpenAI(**kwargs)

    @staticmethod
    def _to_openai_messages(
        messages: list[LLMMessage],
    ) -> list[dict[str, Any]]:
        """Convert internal messages to OpenAI format."""
        result = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    @staticmethod
    def _to_tool_defs(tools: list[LLMToolDefinition] | None) -> list[dict[str, Any]] | None:
        """Convert internal tool definitions to OpenAI format."""
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[LLMToolDefinition] | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        start = time.monotonic()
        model_name = model or self.model

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        tool_defs = self._to_tool_defs(tools)
        if tool_defs:
            kwargs["tools"] = tool_defs
        if stop:
            kwargs["stop"] = stop

        response = await self.client.chat.completions.create(**kwargs)
        latency_ms = (time.monotonic() - start) * 1000

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            model=model_name,
            latency_ms=latency_ms,
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[LLMToolDefinition] | None = None,
        stop: list[str] | None = None,
    ) -> AsyncIterator[str]:
        model_name = model or self.model

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        tool_defs = self._to_tool_defs(tools)
        if tool_defs:
            kwargs["tools"] = tool_defs
        if stop:
            kwargs["stop"] = stop

        async for chunk in await self.client.chat.completions.create(**kwargs):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ========== Anthropic Client ==========

try:
    from anthropic import AsyncAnthropic

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


class AnthropicClient(LLMClient):
    """Anthropic Claude LLM client."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        base_url: str | None = None,
    ):
        if not _ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic>=0.30.0 is required for AnthropicClient")

        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**kwargs)

    @staticmethod
    def _to_anthropic_messages(
        messages: list[LLMMessage],
    ) -> tuple:
        """Convert internal messages to Anthropic format."""
        system_content = ""
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            elif msg.role == "user":
                chat_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                chat_messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == "tool":
                chat_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id or "",
                                "content": msg.content,
                            }
                        ],
                    }
                )
        return system_content, chat_messages

    @staticmethod
    def _to_tool_defs(tools: list[LLMToolDefinition] | None) -> list[dict[str, Any]] | None:
        """Convert internal tool definitions to Anthropic format."""
        if not tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[LLMToolDefinition] | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        start = time.monotonic()
        model_name = model or self.model
        system_content, chat_messages = self._to_anthropic_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_content:
            kwargs["system"] = system_content
        tool_defs = self._to_tool_defs(tools)
        if tool_defs:
            kwargs["tools"] = tool_defs
        if stop:
            kwargs["stop_sequences"] = stop

        response = await self.client.messages.create(**kwargs)
        latency_ms = (time.monotonic() - start) * 1000

        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input) if isinstance(block.input, dict) else str(block.input),
                        },
                    }
                )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason or "stop",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            model=model_name,
            latency_ms=latency_ms,
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[LLMToolDefinition] | None = None,
        stop: list[str] | None = None,
    ) -> AsyncIterator[str]:
        model_name = model or self.model
        system_content, chat_messages = self._to_anthropic_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_content:
            kwargs["system"] = system_content

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text


# ========== Mock Client (for testing) ==========


class MockLLMClient(LLMClient):
    """Mock LLM client for testing. Returns predefined responses."""

    def __init__(self, response: str = "mock response", tool_calls: list[dict] | None = None):
        self.response = response
        self.tool_calls = tool_calls or []
        self.call_history: list[dict] = []

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: list[LLMToolDefinition] | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        self.call_history.append(
            {
                "messages": [(m.role, m.content) for m in messages],
                "model": model,
                "temperature": temperature,
                "tools": [t.name for t in tools] if tools else [],
            }
        )
        return LLMResponse(
            content=self.response,
            tool_calls=self.tool_calls,
            model=model or "mock",
            latency_ms=10.0,
        )
