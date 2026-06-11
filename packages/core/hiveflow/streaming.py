"""HiveFlow - Streaming Utilities

Provides streaming response handling for LLM outputs and workflow execution.
Supports Server-Sent Events (SSE) and async iteration patterns.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StreamEventType(str, Enum):
    """Types of streaming events."""

    TOKEN = "token"  # LLM token
    THOUGHT = "thought"  # Agent thinking
    TOOL_CALL = "tool_call"  # Tool being called
    TOOL_RESULT = "tool_result"  # Tool result
    CHECKPOINT = "checkpoint"  # Checkpoint saved
    NODE_START = "node_start"  # Workflow node starting
    NODE_END = "node_end"  # Workflow node completed
    ERROR = "error"  # Error occurred
    DONE = "done"  # Stream complete


@dataclass
class StreamEvent:
    """A single streaming event."""

    type: StreamEventType
    data: Any
    timestamp: float = field(default_factory=time.time)
    node_id: str | None = None
    workflow_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        """Convert to Server-Sent Events format."""
        lines = [
            f"event: {self.type.value}",
            f"data: {json.dumps(self.data, default=str)}",
        ]
        if self.node_id:
            lines.append(f"id: {self.node_id}")
        if self.timestamp:
            lines.append("retry: 3000")
        lines.append("")
        lines.append("")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(
            {
                "type": self.type.value,
                "data": self.data,
                "timestamp": self.timestamp,
                "node_id": self.node_id,
                "workflow_id": self.workflow_id,
                "metadata": self.metadata,
            },
            default=str,
        )


class StreamBuffer:
    """
    Async buffer for streaming events.
    Producers put events, consumers iterate over them.

    Usage:
        buffer = StreamBuffer()

        # Producer
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="Hello"))
        await buffer.close()

        # Consumer
        async for event in buffer:
            print(event.data)
    """

    def __init__(self, max_size: int = 1000):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._closed = False
        self._events: list[StreamEvent] = []

    async def put(self, event: StreamEvent):
        """Put an event into the stream."""
        if self._closed:
            raise RuntimeError("Cannot put to a closed stream")
        self._events.append(event)
        await self._queue.put(event)

    async def close(self):
        """Close the stream, signaling no more events."""
        self._closed = True
        await self._queue.put(None)  # Sentinel

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        return self

    async def __anext__(self) -> StreamEvent:
        event = await self._queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    def get_events(self) -> list[StreamEvent]:
        """Get all events collected so far."""
        return list(self._events)

    def is_closed(self) -> bool:
        return self._closed


async def collect_stream(buffer: StreamBuffer) -> list[StreamEvent]:
    """Consume all events from a stream buffer and return them."""
    events = []
    async for event in buffer:
        events.append(event)
    return events


def sse_response(events: AsyncIterator[StreamEvent]):
    """
    Create an SSE response from an async iterator of StreamEvents.
    For use in FastAPI StreamingResponse.

    Usage:
        from fastapi.responses import StreamingResponse
        return StreamingResponse(sse_response(event_iter), media_type="text/event-stream")
    """

    async def event_generator():
        async for event in events:
            yield event.to_sse()

    return event_generator()
