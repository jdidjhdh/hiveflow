import os
import openai
from .base import LLMClient
from typing import List


class OpenAILLMClient(LLMClient):
    def __init__(self, model="gpt-4o", api_key=None, base_url=None):
        effective_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not effective_key:
            raise ValueError(
                "OpenAI API key is required. Pass api_key parameter or set OPENAI_API_KEY environment variable."
            )
        self.client = openai.AsyncOpenAI(api_key=effective_key, base_url=base_url)
        self.model = model

    async def complete(self, messages, **kwargs):
        resp = await self.client.chat.completions.create(
            model=self.model, messages=messages, **kwargs
        )
        return resp.choices[0].message.content

    async def stream(self, messages, **kwargs):
        stream = await self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True, **kwargs
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embed(self, texts: List[str]) -> List[List[float]]:
        resp = await self.client.embeddings.create(
            input=texts, model="text-embedding-3-small"
        )
        return [d.embedding for d in resp.data]
