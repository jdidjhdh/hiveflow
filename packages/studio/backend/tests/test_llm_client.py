"""HiveFlow - LLM Client tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import LLMClient, LLMMessage, LLMToolDefinition, LLMResponse, MockLLMClient


# ========== MockLLMClient Tests ==========

@pytest.mark.asyncio
async def test_mock_client_returns_predefined_response():
    client = MockLLMClient(response="Hello, world!")
    messages = [LLMMessage(role="user", content="Say hello")]
    resp = await client.chat(messages)
    assert resp.content == "Hello, world!"


@pytest.mark.asyncio
async def test_mock_client_records_call_history():
    client = MockLLMClient(response="ok")
    messages = [
        LLMMessage(role="system", content="You are helpful"),
        LLMMessage(role="user", content="Test"),
    ]
    await client.chat(messages, model="gpt-4", temperature=0.5, tools=[
        LLMToolDefinition(name="search", description="Search", parameters={})
    ])

    assert len(client.call_history) == 1
    call = client.call_history[0]
    assert call["model"] == "gpt-4"
    assert call["temperature"] == 0.5
    assert call["tools"] == ["search"]
    assert call["messages"][0] == ("system", "You are helpful")


@pytest.mark.asyncio
async def test_mock_client_returns_tool_calls():
    tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "search", "arguments": "{}"}}]
    client = MockLLMClient(response="", tool_calls=tool_calls)
    resp = await client.chat([LLMMessage(role="user", content="search something")])
    assert resp.tool_calls == tool_calls


@pytest.mark.asyncio
async def test_mock_response_fields():
    client = MockLLMClient(response="test")
    resp = await client.chat([LLMMessage(role="user", content="test")], model="test-model")
    assert resp.model == "test-model"
    assert resp.finish_reason == "stop"
    assert resp.latency_ms == 10.0
    assert resp.usage == {}


@pytest.mark.asyncio
async def test_mock_client_stream():
    client = MockLLMClient(response="streamed response")
    messages = [LLMMessage(role="user", content="stream")]
    chunks = []
    async for chunk in client.chat_stream(messages):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert chunks[0] == "streamed response"


# ========== LLMMessage Tests ==========

def test_llm_message_creation():
    msg = LLMMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.tool_calls is None
    assert msg.tool_call_id is None


def test_llm_message_with_tool_calls():
    tool_calls = [{"id": "1", "type": "function"}]
    msg = LLMMessage(role="assistant", content="", tool_calls=tool_calls)
    assert msg.tool_calls == tool_calls


def test_llm_message_with_tool_call_id():
    msg = LLMMessage(role="tool", content="result", tool_call_id="call_1")
    assert msg.tool_call_id == "call_1"


# ========== LLMToolDefinition Tests ==========

def test_tool_definition_creation():
    tool = LLMToolDefinition(
        name="search",
        description="Search the web",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    assert tool.name == "search"
    assert tool.description == "Search the web"
    assert tool.parameters["properties"]["query"]["type"] == "string"


# ========== LLMResponse Tests ==========

def test_llm_response_defaults():
    resp = LLMResponse(content="test")
    assert resp.content == "test"
    assert resp.tool_calls == []
    assert resp.finish_reason == "stop"
    assert resp.usage == {}
    assert resp.model == ""
    assert resp.latency_ms == 0.0


def test_llm_response_with_values():
    resp = LLMResponse(
        content="",
        tool_calls=[{"id": "1"}],
        finish_reason="tool_calls",
        usage={"total_tokens": 100},
        model="gpt-4",
        latency_ms=250.5,
    )
    assert resp.finish_reason == "tool_calls"
    assert resp.usage["total_tokens"] == 100
    assert resp.model == "gpt-4"
    assert resp.latency_ms == 250.5
