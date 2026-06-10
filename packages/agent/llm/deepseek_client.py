import os
from typing import List
from .base import LLMClient


class DeepSeekLLMClient(LLMClient):
    """DeepSeek LLM 客户端 (OpenAI 兼容 API)。"""
    def __init__(self, model="deepseek-chat", api_key=None, base_url=None):
        try:
            import openai
        except ImportError:
            raise ImportError("openai package is required for DeepSeek client")

        effective_key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not effective_key:
            raise ValueError(
                "DeepSeek API key is required. Pass api_key, set DEEPSEEK_API_KEY, or set OPENAI_API_KEY."
            )
        default_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.client = openai.AsyncOpenAI(api_key=effective_key, base_url=default_url)
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
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def embed(self, texts: List[str]) -> List[List[float]]:
        # DeepSeek doesn't have embedding; return simple hash-based vectors
        import hashlib
        vectors = []
        for text in texts:
            h = hashlib.md5(text.encode()).digest()
            vectors.append([float(b) / 255.0 for b in h] * 96)  # 1536 dim
        return vectors
