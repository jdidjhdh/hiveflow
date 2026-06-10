"""HiveFlow - ReActWorker tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import LLMClient, LLMMessage, LLMToolDefinition, LLMResponse, MockLLMClient
from hiveflow.react_worker import (
    ReActWorker, ReActTool,
    create_read_blackboard_tool,
    create_write_blackboard_tool,
    create_python_code_tool,
    create_default_tools,
    REACT_SYSTEM_PROMPT,
)


# ========== ReActWorker Tests ==========

@pytest.mark.asyncio
async def test_react_worker_no_tools():
    """Worker without tools should return LLM response directly."""
    client = MockLLMClient(response="The answer is 42")
    worker = ReActWorker(llm_client=client)

    result = await worker.execute("What is 6*7?")

    assert result["answer"] == "The answer is 42"
    assert result["tool_calls"] == []
    assert result["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_react_worker_with_tool_calls():
    """Worker should call tools and use results."""
    # First response: call the calculator tool
    # Second response: give final answer
    call_count = [0]

    class MockWithTools(LLMClient):
        async def chat(self, messages, model="", temperature=0.0, max_tokens=4096, tools=None, stop=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return LLMResponse(
                    content="I need to calculate this",
                    tool_calls=[{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "calculator", "arguments": '{"expression": "2+3"}'},
                    }],
                )
            else:
                return LLMResponse(content="The result is 5")

    client = MockWithTools()

    def calc_handler(args):
        expr = args.get("expression", "")
        return eval(expr)

    calc_tool = ReActTool(
        name="calculator",
        description="Evaluate a math expression",
        parameters={"type": "object", "properties": {"expression": {"type": "string"}}},
        handler=calc_handler,
    )

    worker = ReActWorker(llm_client=client, tools=[calc_tool])
    result = await worker.execute("Calculate 2+3")

    assert call_count[0] == 2  # 1 tool call + 1 final answer
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "calculator"
    assert result["tool_calls"][0]["result"] == 5


@pytest.mark.asyncio
async def test_react_worker_respects_max_iterations():
    """Worker should stop after max_iterations."""
    call_count = [0]

    class LoopClient(LLMClient):
        async def chat(self, messages, model="", temperature=0.0, max_tokens=4096, tools=None, stop=None):
            call_count[0] += 1
            # Always return a tool call to force iteration
            return LLMResponse(
                content="",
                tool_calls=[{
                    "id": f"call_{call_count[0]}",
                    "type": "function",
                    "function": {"name": "noop", "arguments": "{}"},
                }],
            )

    client = LoopClient()
    noop_tool = ReActTool(
        name="noop",
        description="Do nothing",
        parameters={"type": "object", "properties": {}},
        handler=lambda args: "ok",
    )

    worker = ReActWorker(llm_client=client, tools=[noop_tool], max_iterations=3)
    result = await worker.execute("Test")

    assert call_count[0] <= 3
    assert result["iterations"] <= 3


@pytest.mark.asyncio
async def test_react_worker_handles_tool_error():
    """Worker should handle tool errors gracefully."""
    call_count = [0]

    class ErrorClient(LLMClient):
        async def chat(self, messages, model="", temperature=0.0, max_tokens=4096, tools=None, stop=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "failing_tool", "arguments": "{}"},
                    }],
                )
            return LLMResponse(content="Tool failed, giving up")

    client = ErrorClient()
    failing_tool = ReActTool(
        name="failing_tool",
        description="Always fails",
        parameters={"type": "object", "properties": {}},
        handler=lambda args: (_ for _ in ()).throw(ValueError("Intentional failure")),
    )

    worker = ReActWorker(llm_client=client, tools=[failing_tool])
    result = await worker.execute("Test")

    assert len(result["tool_calls"]) == 1
    assert "Error" in str(result["tool_calls"][0]["result"])


# ========== Built-in Tool Tests ==========

def test_react_tool_definition():
    tool = ReActTool(
        name="test",
        description="Test tool",
        parameters={"type": "object", "properties": {}},
        handler=lambda args: "ok",
    )
    assert tool.name == "test"
    assert tool.description == "Test tool"
    assert callable(tool.handler)


@pytest.mark.asyncio
async def test_python_code_tool_simple_eval():
    tool = create_python_code_tool()
    result = await tool.handler({"code": "2 + 3"})
    assert result["result"] == 5
    assert result["type"] == "int"


@pytest.mark.asyncio
async def test_python_code_tool_with_imports():
    tool = create_python_code_tool()
    # Sandbox should block imports — this is expected secure behavior
    result = await tool.handler({"code": "import math\n_result = math.pi"})
    assert "error" in result  # __import__ not found (sandbox working)


@pytest.mark.asyncio
async def test_python_code_tool_rejects_dangerous_code():
    """Python tool should not allow dangerous operations."""
    tool = create_python_code_tool()
    result = await tool.handler({"code": "import os; os.system('echo hacked')"})
    assert "error" in result


@pytest.mark.asyncio
async def test_python_code_tool_max_length():
    tool = create_python_code_tool()
    result = await tool.handler({"code": "x = " + "1" * 6000})
    assert "error" in result
    assert "too long" in result["error"]


@pytest.mark.asyncio
async def test_read_blackboard_tool():
    async def mock_get(key):
        if key == "test":
            return {"value": 42}
        raise KeyError(key)

    tool = create_read_blackboard_tool(mock_get)
    assert tool.name == "read_blackboard"

    # Successful read
    result = await tool.handler({"key": "test"})
    assert result["value"] == {"value": 42}

    # Missing key
    result = await tool.handler({"key": "missing"})
    assert "error" in result


@pytest.mark.asyncio
async def test_write_blackboard_tool():
    written = {}

    async def mock_put(key, value):
        written[key] = value

    tool = create_write_blackboard_tool(mock_put)
    assert tool.name == "write_blackboard"

    result = await tool.handler({"key": "output", "value": {"data": 123}})
    assert result["success"] is True
    assert written["output"] == {"data": 123}

    # Missing key
    result = await tool.handler({"value": "no_key"})
    assert "error" in result


def test_create_default_tools():
    """Should create default tools when handlers provided."""
    async def mock_get(key):
        pass

    async def mock_put(key, value):
        pass

    tools = create_default_tools(blackboard_get=mock_get, blackboard_put=mock_put)
    names = [t.name for t in tools]
    assert "read_blackboard" in names
    assert "write_blackboard" in names
    assert "http_request" in names
    assert "python_code" in names


def test_default_tools_without_handlers():
    """Should only include tools with handlers."""
    tools = create_default_tools()
    names = [t.name for t in tools]
    # No blackboard tools without handlers
    assert "read_blackboard" not in names
    assert "write_blackboard" not in names
    # http_request and python_code should always be included
    assert "http_request" in names
    assert "python_code" in names
