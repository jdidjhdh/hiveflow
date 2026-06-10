import os
import anthropic
from .base import LLMClient
from typing import List


class AnthropicLLMClient(LLMClient):
    def __init__(self, model="claude-sonnet-4-20250514", api_key=None, base_url=None):
        effective_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not effective_key:
            raise ValueError(
                "Anthropic API key is required. Pass api_key parameter or set ANTHROPIC_API_KEY environment variable."
            )
        self.client = anthropic.AsyncAnthropic(api_key=effective_key, base_url=base_url)
        self.model = model

    @staticmethod
    def _convert_messages(messages):
        """Convert OpenAI-style messages to Anthropic format."""
        system_msgs = [m for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]
        system_content = "\n".join([m["content"] for m in system_msgs])
        anthropic_messages = []
        for m in non_system:
            anthropic_messages.append({"role": m["role"], "content": m["content"]})
        return system_content, anthropic_messages

    async def complete(self, messages, **kwargs):
        system_content, anthropic_messages = self._convert_messages(messages)
        resp = await self.client.messages.create(
            model=self.model,
            system=system_content,
            messages=anthropic_messages,
            max_tokens=kwargs.pop("max_tokens", 4096),
            **kwargs
        )
        return resp.content[0].text if resp.content else ""

    async def stream(self, messages, **kwargs):
        system_content, anthropic_messages = self._convert_messages(messages)
        async with self.client.messages.stream(
            model=self.model,
            system=system_content,
            messages=anthropic_messages,
            max_tokens=kwargs.pop("max_tokens", 4096),
            **kwargs
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("Anthropic does not support embeddings")
