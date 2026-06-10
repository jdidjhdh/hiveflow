from abc import ABC, abstractmethod
from typing import Any, Dict, List, AsyncGenerator
import json
import logging

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str: ...

    async def complete_json(self, messages, max_retries=3, max_messages=30, **kwargs) -> Dict[str, Any]:
        """解析 JSON 响应，带重试和长度限制防止上下文溢出"""
        for attempt in range(max_retries):
            text = await self.complete(messages, **kwargs)
            try:
                json_text = text
                if "```" in text:
                    parts = text.split("```")
                    for i in range(1, len(parts), 2):
                        if parts[i].strip().startswith("json"):
                            json_text = parts[i].strip()[4:]
                            break
                return json.loads(json_text)
            except json.JSONDecodeError:
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": "Invalid JSON. Output only valid JSON without markdown."})
                if len(messages) > max_messages:
                    system_msgs = [m for m in messages if m["role"] == "system"]
                    non_system = [m for m in messages if m["role"] != "system"]
                    keep = max(2, max_messages - len(system_msgs))
                    messages[:] = system_msgs + non_system[-keep:]
                logger.warning(f"JSON parse attempt {attempt+1} failed, retrying...")
        raise ValueError("LLM did not return valid JSON after max retries")

    @abstractmethod
    async def stream(self, messages, **kwargs) -> AsyncGenerator[str, None]: ...

    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError
