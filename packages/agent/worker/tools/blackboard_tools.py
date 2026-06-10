import json
from abc import ABC, abstractmethod
from typing import Any, Dict


class Tool(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def run(self, input: Dict[str, Any], view) -> Any: ...


class ReadBlackboardTool(Tool):
    name = "read_blackboard"
    description = "Read value from blackboard key"
    parameters = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}

    async def run(self, input, view):
        try:
            val = await view.get(input["key"])
            return json.dumps(val, ensure_ascii=False)
        except KeyError:
            return f"Error: key '{input['key']}' not found"


class WriteBlackboardTool(Tool):
    name = "write_blackboard"
    description = "Write value to blackboard key, optional TTL"
    parameters = {
        "type": "object",
        "properties": {"key": {"type": "string"}, "value": {}, "ttl": {"type": "number"}},
        "required": ["key", "value"]
    }

    async def run(self, input, view):
        try:
            await view.put(input["key"], input["value"], input.get("ttl"))
        except KeyError:
            return f"Error: missing required parameter 'key'"
        return "OK"
