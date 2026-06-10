"""Tests for hiveflow streaming module."""
import pytest
import asyncio
import json
from unittest.mock import MagicMock

from hiveflow import StreamEventType, StreamEvent, StreamBuffer, collect_stream
# Access the streaming module directly for sse_response
import sys
import os
_hf_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'hiveflow')
import importlib.util
_spec = importlib.util.spec_from_file_location("streaming_mod", os.path.join(_hf_dir, "streaming.py"))
streaming_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(streaming_mod)


class TestStreamEventType:
    def test_all_event_types_exist(self):
        assert StreamEventType.TOKEN.value == "token"
        assert StreamEventType.THOUGHT.value == "thought"
        assert StreamEventType.TOOL_CALL.value == "tool_call"
        assert StreamEventType.TOOL_RESULT.value == "tool_result"
        assert StreamEventType.CHECKPOINT.value == "checkpoint"
        assert StreamEventType.NODE_START.value == "node_start"
        assert StreamEventType.NODE_END.value == "node_end"
        assert StreamEventType.ERROR.value == "error"
        assert StreamEventType.DONE.value == "done"

    def test_event_type_is_string_enum(self):
        assert isinstance(StreamEventType.TOKEN, str)
        assert StreamEventType.TOKEN == "token"


class TestStreamEvent:
    def test_create_event_minimal(self):
        event = StreamEvent(type=StreamEventType.TOKEN, data="Hello")
        assert event.type == StreamEventType.TOKEN
        assert event.data == "Hello"
        assert event.node_id is None
        assert event.workflow_id is None
        assert event.metadata == {}
        assert event.timestamp > 0

    def test_create_event_full(self):
        event = StreamEvent(
            type=StreamEventType.NODE_START,
            data={"node": "step1"},
            node_id="n1",
            workflow_id="wf_001",
            metadata={"key": "value"},
        )
        assert event.type == StreamEventType.NODE_START
        assert event.data == {"node": "step1"}
        assert event.node_id == "n1"
        assert event.workflow_id == "wf_001"
        assert event.metadata == {"key": "value"}

    def test_to_sse_format(self):
        event = StreamEvent(type=StreamEventType.TOKEN, data="Hello", node_id="n1")
        sse = event.to_sse()
        assert "event: token" in sse
        assert 'data: "Hello"' in sse
        assert "id: n1" in sse
        assert "retry: 3000" in sse

    def test_to_sse_without_node_id(self):
        event = StreamEvent(type=StreamEventType.DONE, data=None)
        sse = event.to_sse()
        assert "event: done" in sse
        assert "data: null" in sse
        assert "id:" not in sse

    def test_to_json_format(self):
        event = StreamEvent(
            type=StreamEventType.TOOL_CALL,
            data={"tool": "search", "query": "test"},
            node_id="n1",
            workflow_id="wf_001",
            metadata={"call_id": "c1"},
        )
        j = event.to_json()
        parsed = json.loads(j)
        assert parsed["type"] == "tool_call"
        assert parsed["data"]["tool"] == "search"
        assert parsed["node_id"] == "n1"
        assert parsed["workflow_id"] == "wf_001"
        assert parsed["metadata"]["call_id"] == "c1"

    def test_to_json_serializes_non_serializable(self):
        event = StreamEvent(type=StreamEventType.ERROR, data=MagicMock())
        j = event.to_json()  # Should not raise, uses default=str
        parsed = json.loads(j)
        assert parsed["type"] == "error"


@pytest.mark.asyncio
class TestStreamBuffer:
    async def test_put_and_iterate(self):
        buffer = StreamBuffer()
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="A"))
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="B"))
        await buffer.close()

        events = []
        async for event in buffer:
            events.append(event)

        assert len(events) == 2
        assert events[0].data == "A"
        assert events[1].data == "B"

    async def test_close_sets_flag(self):
        buffer = StreamBuffer()
        assert not buffer.is_closed()
        await buffer.close()
        assert buffer.is_closed()

    async def test_put_to_closed_raises(self):
        buffer = StreamBuffer()
        await buffer.close()
        with pytest.raises(RuntimeError, match="closed"):
            await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="X"))

    async def test_get_events_returns_all(self):
        buffer = StreamBuffer()
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="A"))
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="B"))
        events = buffer.get_events()
        assert len(events) == 2
        assert events[0].data == "A"
        assert events[1].data == "B"

    async def test_get_events_returns_copy(self):
        buffer = StreamBuffer()
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="A"))
        events1 = buffer.get_events()
        events1.clear()
        events2 = buffer.get_events()
        assert len(events2) == 1  # Original buffer not affected

    async def test_max_size_limit(self):
        buffer = StreamBuffer(max_size=2)
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="A"))
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="B"))
        # Third put should block or raise if queue is full
        # Since we haven't consumed, this should block indefinitely
        # We test by checking the queue is at capacity
        assert buffer._queue.full()

    async def test_empty_buffer_iteration(self):
        buffer = StreamBuffer()
        await buffer.close()
        events = []
        async for event in buffer:
            events.append(event)
        assert len(events) == 0


@pytest.mark.asyncio
class TestCollectStream:
    async def test_collect_all_events(self):
        buffer = StreamBuffer()
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="A"))
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="B"))
        await buffer.put(StreamEvent(type=StreamEventType.DONE, data=None))
        await buffer.close()

        events = await collect_stream(buffer)
        assert len(events) == 3
        assert events[0].data == "A"
        assert events[2].type == StreamEventType.DONE

    async def test_collect_empty_stream(self):
        buffer = StreamBuffer()
        await buffer.close()
        events = await collect_stream(buffer)
        assert events == []


class TestSSEResponse:
    def test_sse_response_returns_generator(self):
        async def gen_events():
            yield StreamEvent(type=StreamEventType.TOKEN, data="Hello")
            yield StreamEvent(type=StreamEventType.DONE, data=None)

        result = streaming_mod.sse_response(gen_events())
        # Should return an async generator
        assert hasattr(result, '__aiter__')

    @pytest.mark.asyncio
    async def test_sse_response_yields_sse_format(self):
        async def gen_events():
            yield StreamEvent(type=StreamEventType.TOKEN, data="Hello")

        result = streaming_mod.sse_response(gen_events())
        chunks = []
        async for chunk in result:
            chunks.append(chunk)

        assert len(chunks) == 1
        assert "event: token" in chunks[0]
        assert 'data: "Hello"' in chunks[0]
