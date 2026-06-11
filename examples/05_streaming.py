"""
HiveFlow - 05: Streaming Responses

This example demonstrates streaming events for real-time feedback.

Usage:
    python 05_streaming.py
"""
import asyncio
from hiveflow import StreamBuffer, StreamEvent, StreamEventType


async def simulate_streaming_workflow(buffer: StreamBuffer) -> None:
    """Simulate an agent emitting streaming events."""
    await buffer.put(StreamEvent(type=StreamEventType.NODE_START, data={"node": "writer"}, node_id="writer"))
    for token in ["The ", "future ", "of ", "AI ", "is ", "bright."]:
        await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data=token, node_id="writer"))
        await asyncio.sleep(0.05)
    await buffer.put(StreamEvent(type=StreamEventType.THOUGHT, data="Draft complete", node_id="writer"))
    await buffer.put(StreamEvent(type=StreamEventType.NODE_END, data={"node": "writer"}, node_id="writer"))
    await buffer.put(StreamEvent(type=StreamEventType.DONE, data=None))
    await buffer.close()


async def main():
    print("=== Streaming Example ===\n")

    buffer = StreamBuffer()
    producer = asyncio.create_task(simulate_streaming_workflow(buffer))

    print("Streaming output:")
    async for event in buffer:
        if event.type == StreamEventType.TOKEN:
            print(event.data, end="", flush=True)
        elif event.type == StreamEventType.THOUGHT:
            print(f"\n[Thought: {event.data}]")
        elif event.type == StreamEventType.NODE_START:
            print(f"\n--- Starting node: {event.node_id} ---")
        elif event.type == StreamEventType.NODE_END:
            print(f"\n--- Completed node: {event.node_id} ---")
        elif event.type == StreamEventType.DONE:
            print("\n\nDone.")

    await producer
    print("\nUse StreamBuffer with FastAPI StreamingResponse for SSE endpoints.")


if __name__ == "__main__":
    asyncio.run(main())
