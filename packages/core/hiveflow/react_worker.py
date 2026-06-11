"""HiveFlow - ReActWorker

Reasoning-Acting-Observing worker that uses LLM to solve tasks through
iterative tool use. Follows the ReAct paradigm:
  Thought -> Action -> Observation -> Thought -> ... -> Final Answer
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

try:
    from . import LLMClient, LLMMessage, LLMToolDefinition
except ImportError:
    from hiveflow import LLMClient, LLMMessage, LLMToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class ReActTool:
    """A tool available to the ReActWorker."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[[dict[str, Any]], Any]  # Sync or async handler


REACT_SYSTEM_PROMPT = """You are a ReAct agent that solves tasks by reasoning and using tools.

Follow this cycle:
1. **Thought**: Think about what to do next
2. **Action**: Call a tool (use tool_calls)
3. **Observation**: See the tool's result
4. Repeat until you have enough information
5. **Final Answer**: Provide the final answer when done

Rules:
- Use tools only when necessary
- Think before each action
- When you have the answer, stop calling tools and give the final answer
- If a tool fails, try an alternative approach
"""


class ReActWorker:
    """
    ReAct-style worker that uses LLM + tools to solve tasks.

    Usage:
        worker = ReActWorker(llm_client=client, tools=[my_tool])
        result = await worker.execute(task="Research Python async patterns", max_iterations=10)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tools: list[ReActTool] | None = None,
        system_prompt: str = "",
        model: str = "",
        max_iterations: int = 15,
    ):
        self.llm_client = llm_client
        self.tools = tools or []
        self.system_prompt = system_prompt or REACT_SYSTEM_PROMPT
        self.model = model
        self.max_iterations = max_iterations
        self._tool_map: dict[str, ReActTool] = {t.name: t for t in self.tools}
        self._iteration_history: list[dict[str, Any]] = []

    def _get_tool_definitions(self) -> list[LLMToolDefinition]:
        return [
            LLMToolDefinition(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in self.tools
        ]

    async def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        tool = self._tool_map.get(tool_name)
        if tool is None:
            return f"Error: tool '{tool_name}' not found"
        try:
            result = tool.handler(arguments)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as e:
            return f"Error: {e!s}"

    async def execute(
        self,
        task: str,
        max_iterations: int = 0,
        blackboard_put=None,  # Optional callback: (key, value) for writing results
    ) -> dict[str, Any]:
        """
        Execute a task using ReAct reasoning.

        Args:
            task: The task description
            max_iterations: Override max iterations (0 = use default)
            blackboard_put: Optional callback (key, value) to write results to blackboard

        Returns:
            Dict with 'answer', 'tool_calls', 'iterations', 'latency_ms'
        """
        start_time = time.monotonic()
        max_iter = max_iterations or self.max_iterations
        tool_calls_made: list[dict[str, Any]] = []

        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=f"Task: {task}"),
        ]

        final_answer = ""

        for iteration in range(max_iter):
            response = await self.llm_client.chat(
                messages=messages,
                model=self.model,
                temperature=0.0,
                max_tokens=1024,
                tools=self._get_tool_definitions() if self.tools else None,
            )

            messages.append(
                LLMMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls if response.tool_calls else None,
                )
            )

            if response.tool_calls:
                # Execute each tool call
                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        arguments = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}

                    observation = await self._call_tool(tool_name, arguments)
                    observation_str = (
                        json.dumps(observation) if isinstance(observation, (dict, list)) else str(observation)
                    )

                    messages.append(
                        LLMMessage(
                            role="tool",
                            content=observation_str,
                            tool_call_id=tc["id"],
                        )
                    )

                    tool_calls_made.append(
                        {
                            "tool": tool_name,
                            "arguments": arguments,
                            "result": observation,
                        }
                    )

                    if blackboard_put:
                        await blackboard_put(f"tool_result.{tool_name}", observation)

                self._iteration_history.append(
                    {
                        "iteration": iteration + 1,
                        "tool_calls": len(response.tool_calls),
                    }
                )
                continue

            # No tool calls = final answer
            if response.content:
                final_answer = response.content
            elif response.finish_reason == "stop":
                final_answer = response.content or "No answer provided"
            break

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return {
            "answer": final_answer,
            "tool_calls": tool_calls_made,
            "iterations": len(self._iteration_history),
            "latency_ms": elapsed_ms,
        }


# ========== Built-in Tools ==========


def create_read_blackboard_tool(blackboard_get):
    """Create a tool that reads from the blackboard.

    Args:
        blackboard_get: async function(key) -> value
    """

    async def handler(args):
        key = args.get("key", "")
        if not key:
            return {"error": "key is required"}
        try:
            value = await blackboard_get(key)
            return {"value": value}
        except KeyError:
            return {"error": f"key '{key}' not found"}
        except Exception as e:
            return {"error": str(e)}

    return ReActTool(
        name="read_blackboard",
        description="Read a value from the shared blackboard by key",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The blackboard key to read"},
            },
            "required": ["key"],
        },
        handler=handler,
    )


def create_write_blackboard_tool(blackboard_put):
    """Create a tool that writes to the blackboard.

    Args:
        blackboard_put: async function(key, value) -> None
    """

    async def handler(args):
        key = args.get("key", "")
        value = args.get("value")
        if not key:
            return {"error": "key is required"}
        try:
            await blackboard_put(key, value)
            return {"success": True, "key": key}
        except Exception as e:
            return {"error": str(e)}

    return ReActTool(
        name="write_blackboard",
        description="Write a value to the shared blackboard",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The blackboard key"},
                "value": {"description": "The value to write (must be JSON-serializable)"},
            },
            "required": ["key", "value"],
        },
        handler=handler,
    )


def create_http_request_tool():
    """Create a tool that makes HTTP GET requests."""
    import httpx

    async def handler(args):
        url = args.get("url", "")
        if not url:
            return {"error": "url is required"}
        method = args.get("method", "GET").upper()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(method, url)
                return {
                    "status_code": response.status_code,
                    "body": response.text[:4000],  # Limit response size
                    "headers": dict(response.headers),
                }
        except Exception as e:
            return {"error": str(e)}

    return ReActTool(
        name="http_request",
        description="Make an HTTP request to a URL",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to request"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
            },
            "required": ["url"],
        },
        handler=handler,
    )


def create_search_tool(search_fn):
    """Create a tool that searches for information.

    Args:
        search_fn: async function(query) -> List[Dict]
    """

    async def handler(args):
        query = args.get("query", "")
        if not query:
            return {"error": "query is required"}
        try:
            results = await search_fn(query)
            return {"results": results[:5], "count": len(results)}
        except Exception as e:
            return {"error": str(e)}

    return ReActTool(
        name="search",
        description="Search for information using the knowledge base",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
        handler=handler,
    )


def create_python_code_tool():
    """Create a tool that executes Python code safely (sandboxed)."""

    async def handler(args):
        code = args.get("code", "")
        if not code:
            return {"error": "code is required"}
        if len(code) > 5000:
            return {"error": "code too long (max 5000 chars)"}

        # Restricted execution: only allow safe builtins
        import builtins

        allowed_builtins = {
            "len",
            "str",
            "int",
            "float",
            "list",
            "dict",
            "set",
            "tuple",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "sorted",
            "reversed",
            "min",
            "max",
            "sum",
            "abs",
            "round",
            "bool",
            "type",
            "isinstance",
            "print",
            "repr",
            "format",
            "join",
            "split",
            "strip",
            "replace",
            "True",
            "False",
            "None",
        }
        safe_builtins = {k: v for k, v in vars(builtins).items() if k in allowed_builtins}

        import datetime
        import json
        import math
        import re

        safe_globals = {
            "__builtins__": safe_builtins,
            "math": math,
            "datetime": datetime,
            "json": json,
            "re": re,
        }

        try:
            # Use eval for expressions, exec for statements
            result = None
            if "\n" not in code and not code.startswith(("for", "if", "while", "def", "class")):
                result = eval(code, safe_globals)
            else:
                exec(code, safe_globals)
                result = safe_globals.get("_result", "executed successfully")
            return {"result": result, "type": type(result).__name__}
        except Exception as e:
            return {"error": str(e)}

    return ReActTool(
        name="python_code",
        description="Execute Python code in a safe sandboxed environment",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The Python code to execute"},
            },
            "required": ["code"],
        },
        handler=handler,
    )


def create_default_tools(
    blackboard_get=None,
    blackboard_put=None,
    search_fn=None,
) -> list[ReActTool]:
    """Create a set of default tools for the ReActWorker."""
    tools = []
    if blackboard_get:
        tools.append(create_read_blackboard_tool(blackboard_get))
    if blackboard_put:
        tools.append(create_write_blackboard_tool(blackboard_put))
    tools.append(create_http_request_tool())
    if search_fn:
        tools.append(create_search_tool(search_fn))
    tools.append(create_python_code_tool())
    return tools
