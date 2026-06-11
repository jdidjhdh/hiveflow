"""Tests for hiveflow.react_worker module."""
import json

import pytest

from hiveflow import LLMResponse
from hiveflow.react_worker import (
    ReActTool,
    ReActWorker,
    create_default_tools,
    create_python_code_tool,
    create_read_blackboard_tool,
    create_search_tool,
    create_write_blackboard_tool,
)


class SequentialMockLLM:
    """Returns a sequence of LLM responses for multi-turn ReAct loops."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self._index = 0
        self.call_history: list[dict] = []

    async def chat(self, messages, model="", temperature=0.0, max_tokens=4096, tools=None, stop=None):
        self.call_history.append({"messages": len(messages), "tools": len(tools or [])})
        if self._index >= len(self._responses):
            return LLMResponse(content="fallback", model="mock", latency_ms=1.0)
        response = self._responses[self._index]
        self._index += 1
        return response


@pytest.mark.asyncio
async def test_react_worker_direct_answer():
    client = SequentialMockLLM([LLMResponse(content="The answer is 42", model="mock", latency_ms=1.0)])
    worker = ReActWorker(llm_client=client)

    result = await worker.execute(task="What is the meaning of life?")

    assert result["answer"] == "The answer is 42"
    assert result["tool_calls"] == []
    assert result["iterations"] == 0
    assert result["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_react_worker_tool_then_answer():
    tool_calls = [{
        "id": "call_1",
        "type": "function",
        "function": {"name": "calc", "arguments": json.dumps({"a": 2, "b": 3})},
    }]
    client = SequentialMockLLM([
        LLMResponse(content="", tool_calls=tool_calls, model="mock", latency_ms=1.0),
        LLMResponse(content="Sum is 5", model="mock", latency_ms=1.0),
    ])

    async def add_handler(args):
        return args["a"] + args["b"]

    tool = ReActTool(
        name="calc",
        description="Add numbers",
        parameters={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
        handler=add_handler,
    )
    worker = ReActWorker(llm_client=client, tools=[tool])

    result = await worker.execute(task="Add 2 and 3")

    assert result["answer"] == "Sum is 5"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["result"] == 5
    assert result["iterations"] == 1


@pytest.mark.asyncio
async def test_react_worker_unknown_tool():
    client = SequentialMockLLM([
        LLMResponse(
            content="",
            tool_calls=[{
                "id": "c1",
                "type": "function",
                "function": {"name": "missing_tool", "arguments": "{}"},
            }],
            model="mock",
            latency_ms=1.0,
        ),
        LLMResponse(content="Done", model="mock", latency_ms=1.0),
    ])
    worker = ReActWorker(llm_client=client, tools=[])

    result = await worker.execute(task="Try missing tool")

    assert "Error: tool 'missing_tool' not found" in str(result["tool_calls"][0]["result"])


@pytest.mark.asyncio
async def test_react_worker_blackboard_callback():
    written = {}

    async def bb_put(key, value):
        written[key] = value

    client = SequentialMockLLM([
        LLMResponse(
            content="",
            tool_calls=[{
                "id": "c1",
                "type": "function",
                "function": {"name": "echo", "arguments": json.dumps({"msg": "hi"})},
            }],
            model="mock",
            latency_ms=1.0,
        ),
        LLMResponse(content="ok", model="mock", latency_ms=1.0),
    ])
    tool = ReActTool(
        name="echo",
        description="Echo",
        parameters={"type": "object", "properties": {"msg": {"type": "string"}}},
        handler=lambda args: args["msg"],
    )
    worker = ReActWorker(llm_client=client, tools=[tool])

    await worker.execute(task="echo", blackboard_put=bb_put)

    assert "tool_result.echo" in written


@pytest.mark.asyncio
async def test_create_read_blackboard_tool():
    store = {"key1": "value1"}

    async def bb_get(key):
        if key not in store:
            raise KeyError(key)
        return store[key]

    tool = create_read_blackboard_tool(bb_get)
    result = await tool.handler({"key": "key1"})
    assert result == {"value": "value1"}

    missing = await tool.handler({"key": "missing"})
    assert "error" in missing


@pytest.mark.asyncio
async def test_create_write_blackboard_tool():
    store = {}

    async def bb_put(key, value):
        store[key] = value

    tool = create_write_blackboard_tool(bb_put)
    result = await tool.handler({"key": "k", "value": {"x": 1}})
    assert result["success"] is True
    assert store["k"] == {"x": 1}


@pytest.mark.asyncio
async def test_create_search_tool():
    async def search_fn(query):
        return [{"content": f"hit for {query}"}]

    tool = create_search_tool(search_fn)
    result = await tool.handler({"query": "hiveflow"})
    assert result["count"] == 1
    assert "hiveflow" in result["results"][0]["content"]


@pytest.mark.asyncio
async def test_create_python_code_tool():
    tool = create_python_code_tool()
    result = await tool.handler({"code": "2 + 2"})
    assert result["result"] == 4


@pytest.mark.asyncio
async def test_create_default_tools():
    async def bb_get(key):
        return "v"

    async def bb_put(key, value):
        return None

    async def search_fn(q):
        return []

    tools = create_default_tools(
        blackboard_get=bb_get,
        blackboard_put=bb_put,
        search_fn=search_fn,
    )
    names = {t.name for t in tools}
    assert "read_blackboard" in names
    assert "write_blackboard" in names
    assert "http_request" in names
    assert "search" in names
    assert "python_code" in names
