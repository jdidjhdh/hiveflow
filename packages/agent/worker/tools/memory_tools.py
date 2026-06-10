import json
from abc import ABC, abstractmethod
from typing import Any, Dict


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, input: Dict[str, Any], view) -> Any: ...


class RecallMemoryTool(Tool):
    name = "recall_memory"
    description = "Retrieve relevant info from long-term memory"
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "k": {"type": "integer", "default": 3}},
        "required": ["query"]
    }

    def __init__(self, mem):
        self.mem = mem

    async def run(self, input, view):
        items = await self.mem.recall_long_term(input["query"], input.get("k", 3))
        return json.dumps([{"content": i.content, "metadata": i.metadata} for i in items], ensure_ascii=False)


class SaveMemoryTool(Tool):
    name = "save_memory"
    description = "Save text to long-term memory"
    parameters = {
        "type": "object",
        "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}},
        "required": ["content"]
    }

    def __init__(self, mem):
        self.mem = mem

    async def run(self, input, view):
        await self.mem.save_long_term(input["content"], input.get("metadata"))
        return "Memory saved"
