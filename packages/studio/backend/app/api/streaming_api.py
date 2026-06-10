"""HiveFlow Studio - Streaming API

Server-Sent Events (SSE) endpoint for real-time streaming of workflow execution.
Supports 9 event types: token, thought, tool_call, tool_result,
checkpoint, node_start, node_end, error, done.
"""
import asyncio
import json
import logging
import time
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["streaming"])

# Global event buffer (in production, use Redis pub/sub)
_stream_buffers: dict[str, asyncio.Queue] = {}


async def _event_generator(workflow_id: str):
    """Generate SSE events from the queue."""
    queue = _stream_buffers.get(workflow_id)
    if not queue:
        yield f"event: error\ndata: {json.dumps({'message': 'No stream for this workflow'})}\n\n"
        return

    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30)
            if event is None:  # Sentinel
                break
            yield f"event: {event.get('type', 'unknown')}\ndata: {json.dumps(event)}\n\n"
    except asyncio.TimeoutError:
        # Send keepalive
        yield ": keepalive\n\n"
    finally:
        _stream_buffers.pop(workflow_id, None)


@router.get("")
async def stream_events(workflow_id: Optional[str] = Query(None)):
    """
    SSE endpoint for real-time event streaming.

    Connects to a workflow's event stream and receives events as they occur.
    If no workflow_id is provided, connects to a demo stream.
    """
    if workflow_id:
        if workflow_id not in _stream_buffers:
            _stream_buffers[workflow_id] = asyncio.Queue()
        return StreamingResponse(
            _event_generator(workflow_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Demo stream
    async def demo_generator():
        demo_events = [
            {"type": "node_start", "data": {"node_id": "node_1", "name": "LLM Call"}, "timestamp": time.time()},
            {"type": "thought", "data": "Analyzing the user request...", "timestamp": time.time()},
            {"type": "tool_call", "data": {"name": "search", "args": {"query": "AI trends"}}, "timestamp": time.time()},
            {"type": "tool_result", "data": {"result": "Found 5 results"}, "timestamp": time.time()},
            {"type": "token", "data": "Based on my analysis, ", "timestamp": time.time()},
            {"type": "token", "data": "AI trends show significant growth ", "timestamp": time.time()},
            {"type": "token", "data": "in the following areas:", "timestamp": time.time()},
            {"type": "node_end", "data": {"node_id": "node_1", "status": "success"}, "timestamp": time.time()},
            {"type": "checkpoint", "data": {"checkpoint_id": "cp_1"}, "timestamp": time.time()},
            {"type": "done", "data": {"status": "completed"}, "timestamp": time.time()},
        ]
        for event in demo_events:
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        demo_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/{workflow_id}/push")
async def push_event(workflow_id: str, event: dict):
    """Push an event to a workflow's stream."""
    if workflow_id not in _stream_buffers:
        _stream_buffers[workflow_id] = asyncio.Queue()
    await _stream_buffers[workflow_id].put(event)
    return {"status": "pushed"}


@router.post("/{workflow_id}/close")
async def close_stream(workflow_id: str):
    """Close a workflow's stream."""
    if workflow_id in _stream_buffers:
        await _stream_buffers[workflow_id].put(None)  # Sentinel
    return {"status": "closed"}
