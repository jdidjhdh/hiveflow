import os
import httpx
from .base import LLMClient
from typing import List


class OllamaLLMClient(LLMClient):
    def __init__(self, model="llama3.1", base_url=None):
        self.model = model
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    async def complete(self, messages, **kwargs):
        timeout = kwargs.pop("timeout", 120.0)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **kwargs,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    async def stream(self, messages, **kwargs):
        timeout = kwargs.pop("timeout", 120.0)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content

    async def embed(self, texts: List[str]) -> List[List[float]]:
        payload = {"model": self.model, "input": texts}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/api/embed", json=payload)
            resp.raise_for_status()
            return resp.json()["embeddings"]
