import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from worker.react_worker import ReActWorker
from worker.tools import Tool


# --- Mock Tool ---
class MockTool(Tool):
    def __init__(self, name="mock_tool", description="A mock tool", parameters=None, side_effect=None):
        self._name = name
        self._description = description
        self._parameters = parameters or {}
        self._side_effect = side_effect

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def parameters(self):
        return self._parameters

    async def run(self, input_data, view):
        if self._side_effect:
            return await self._side_effect(input_data, view)
        return f"Result from {self._name} with input {input_data}"


# --- Mock LLM ---
class MockLLM:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0

    async def complete_json(self, messages):
        resp = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return resp


# --- Mock ECM / View ---
class MockECM:
    def __init__(self, payload=None):
        self.payload = payload or {}
        self.user_query = ""
        self.expectation = None


class MockView:
    def __init__(self, data=None):
        self._data = data or {}

    async def get(self, key):
        if key in self._data:
            return self._data[key]
        raise KeyError(key)

    async def put(self, key, value):
        self._data[key] = value


@pytest.mark.asyncio
async def test_react_final_answer():
    llm = MockLLM(responses=[{"type": "final_answer", "content": "42"}])
    worker = ReActWorker(agent_id="test-1", llm=llm, tools=[])
    ecm = MockECM(payload={"query": "What is the answer?"})
    view = MockView()
    result = await worker._run(ecm, view)
    assert result == "42"


@pytest.mark.asyncio
async def test_react_tool_call():
    async def tool_side_effect(input_data, view):
        return f"Computed: {input_data.get('value', 0) * 2}"

    tool = MockTool(name="double", side_effect=tool_side_effect)
    llm = MockLLM(responses=[
        {"type": "tool_call", "tool": "double", "input": {"value": 21}},
        {"type": "final_answer", "content": "42"}
    ])
    worker = ReActWorker(agent_id="test-2", llm=llm, tools=[tool])
    ecm = MockECM(payload={"query": "Double 21"})
    view = MockView()
    result = await worker._run(ecm, view)
    assert result == "42"


@pytest.mark.asyncio
async def test_react_unknown_tool():
    llm = MockLLM(responses=[
        {"type": "tool_call", "tool": "unknown", "input": {}},
        {"type": "final_answer", "content": "done"}
    ])
    worker = ReActWorker(agent_id="test-3", llm=llm, tools=[])
    ecm = MockECM(payload={"query": "test"})
    view = MockView()
    result = await worker._run(ecm, view)
    assert result == "done"


@pytest.mark.asyncio
async def test_react_tool_error():
    async def failing_tool(input_data, view):
        raise RuntimeError("Tool crashed")

    tool = MockTool(name="crash", side_effect=failing_tool)
    llm = MockLLM(responses=[
        {"type": "tool_call", "tool": "crash", "input": {}},
        {"type": "final_answer", "content": "recovered"}
    ])
    worker = ReActWorker(agent_id="test-4", llm=llm, tools=[tool])
    ecm = MockECM(payload={"query": "test"})
    view = MockView()
    result = await worker._run(ecm, view)
    assert result == "recovered"


@pytest.mark.asyncio
async def test_react_max_steps_exceeded():
    llm = MockLLM(responses=[{"type": "tool_call", "tool": "loop", "input": {}}])
    tool = MockTool(name="loop")
    worker = ReActWorker(agent_id="test-5", llm=llm, tools=[tool], max_steps=3)
    ecm = MockECM(payload={"query": "test"})
    view = MockView()
    with pytest.raises(TimeoutError, match="exceeded max steps"):
        await worker._run(ecm, view)


@pytest.mark.asyncio
async def test_react_task_handler_catch_exception():
    llm = MockLLM(responses=[{"type": "final_answer", "content": "ok"}])
    worker = ReActWorker(agent_id="test-6", llm=llm, tools=[])
    ecm = MockECM(payload={"query": "test"})
    view = MockView()

    # Should not raise — handler catches exceptions
    result = await worker.task_handler(ecm, view)
    assert result == "ok"


@pytest.mark.asyncio
async def test_react_with_input_keys():
    view = MockView({"hivemind:result:intent:upstream": {"data": "hello"}})
    llm = MockLLM(responses=[{"type": "final_answer", "content": "done"}])
    worker = ReActWorker(agent_id="test-7", llm=llm, tools=[])
    ecm = MockECM(payload={
        "query": "test",
        "input_keys": {"upstream": "hivemind:result:intent:upstream"}
    })
    result = await worker._run(ecm, view)
    assert result == "done"


@pytest.mark.asyncio
async def test_react_unavailable_input_key():
    view = MockView({})
    llm = MockLLM(responses=[{"type": "final_answer", "content": "done"}])
    worker = ReActWorker(agent_id="test-8", llm=llm, tools=[])
    ecm = MockECM(payload={
        "query": "test",
        "input_keys": {"missing": "hivemind:result:intent:missing"}
    })
    result = await worker._run(ecm, view)
    assert result == "done"
