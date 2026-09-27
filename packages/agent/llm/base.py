import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Base LLM client with security fixes for timeout and retry handling."""
    
    # 🔒 SECURITY: Default stream timeout to prevent event loop blocking
    DEFAULT_STREAM_TIMEOUT = 60.0
    
    @abstractmethod
    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str: ...

    async def complete_json(self, messages, max_retries=3, max_messages=30, 
                           jitter: float = 0.5, trace_id: str | None = None, **kwargs) -> dict[str, Any]:
        """
        🔒 SECURITY FIX: Add jitter to prevent retry storm.
        🔧 OBSERVABILITY FIX: Add trace_id for request tracking.
        🔄 P0 FIX: Use local_messages copy to prevent polluting external message list.
        
        Args:
            messages: Chat messages
            max_retries: Maximum retry attempts
            max_messages: Maximum messages before truncation
            jitter: Random delay factor (0-0.5s) to prevent synchronized retries
            trace_id: 🔧 Trace ID for observability (logged in every request)
        """
        # 🔄 P0 FIX: Create a local copy to avoid polluting the external messages list
        local_messages = messages.copy()
        
        # 🔧 OBSERVABILITY: Log trace_id at start
        if trace_id:
            logger.info(f"[trace_id={trace_id}] complete_json started (max_retries={max_retries})")
        
        for attempt in range(max_retries):
            # 🔧 OBSERVABILITY: Include trace_id in kwargs for downstream logging
            effective_kwargs = kwargs.copy()
            if trace_id:
                effective_kwargs["trace_id"] = trace_id
            
            text = await self.complete(local_messages, **effective_kwargs)
            
            # 🔧 OBSERVABILITY: Log each attempt with trace_id
            if trace_id:
                logger.debug(f"[trace_id={trace_id}] attempt {attempt+1}/{max_retries} response length={len(text)}")
            
            try:
                json_text = text
                if "```" in text:
                    parts = text.split("```")
                    for i in range(1, len(parts), 2):
                        if parts[i].strip().startswith("json"):
                            json_text = parts[i].strip()[4:]
                            break
                result = json.loads(json_text)
                
                # 🔧 OBSERVABILITY: Log success
                if trace_id:
                    logger.info(f"[trace_id={trace_id}] complete_json succeeded on attempt {attempt+1}")
                
                return result
            except json.JSONDecodeError as e:
                # 🔄 P0 FIX: Append to local_messages, not external messages
                local_messages.append({"role": "assistant", "content": text})
                local_messages.append({"role": "user", "content": "Invalid JSON. Output only valid JSON without markdown."})
                if len(local_messages) > max_messages:
                    system_msgs = [m for m in local_messages if m["role"] == "system"]
                    non_system = [m for m in local_messages if m["role"] != "system"]
                    keep = max(2, max_messages - len(system_msgs))
                    local_messages = system_msgs + non_system[-keep:]  # 🔄 P0 FIX: Replace local_messages, not modify in-place
                
                # 🔧 OBSERVABILITY: Log parse failure with details
                if trace_id:
                    logger.warning(f"[trace_id={trace_id}] JSON parse failed on attempt {attempt+1}: {e!s}")
                else:
                    logger.warning(f"JSON parse attempt {attempt+1} failed, retrying...")
                
                # 🔒 SECURITY FIX: Add jitter delay before retry
                if attempt < max_retries - 1:
                    delay = random.uniform(0, jitter)
                    await asyncio.sleep(delay)
        
        # 🔧 OBSERVABILITY: Log final failure
        if trace_id:
            logger.error(f"[trace_id={trace_id}] complete_json failed after {max_retries} attempts")
        
        raise ValueError("LLM did not return valid JSON after max retries")

    @abstractmethod
    async def _stream_impl(self, messages, **kwargs) -> AsyncGenerator[str, None]:
        """Internal stream implementation (subclass must implement)."""
        ...

    async def stream(self, messages, timeout: float | None = None, trace_id: str | None = None, **kwargs) -> AsyncGenerator[str, None]:
        """
        🔒 SECURITY FIX: Add timeout wrapper for streaming to prevent event loop blocking.
        🔧 OBSERVABILITY FIX: Add trace_id for stream tracking.
        
        Args:
            messages: Chat messages
            timeout: Maximum time for streaming (default: 60s)
            trace_id: 🔧 Trace ID for observability
            **kwargs: Additional parameters
        
        Yields:
            str: Streamed content chunks
        
        Raises:
            asyncio.TimeoutError: If streaming exceeds timeout
        """
        effective_timeout = timeout or self.DEFAULT_STREAM_TIMEOUT
        
        # 🔧 OBSERVABILITY: Log stream start
        if trace_id:
            logger.info(f"[trace_id={trace_id}] stream started (timeout={effective_timeout}s)")
        
        # Include trace_id in kwargs for downstream
        effective_kwargs = kwargs.copy()
        if trace_id:
            effective_kwargs["trace_id"] = trace_id
        
        # Wrap streaming with timeout to prevent blocking event loop
        async def _stream_with_timeout():
            async for chunk in self._stream_impl(messages, **effective_kwargs):
                yield chunk
        
        # Create async generator with timeout enforcement
        stream_gen = _stream_with_timeout()
        
        # Use asyncio.wait_for for overall timeout
        # Note: For streaming, we need to check timeout on each chunk
        deadline = asyncio.get_event_loop().time() + effective_timeout
        
        async def _timeout_enforced_stream():
            try:
                chunk_count = 0
                while True:
                    # Check timeout before waiting for next chunk
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        if trace_id:
                            logger.error(f"[trace_id={trace_id}] stream timeout after {effective_timeout}s")
                        raise asyncio.TimeoutError(
                            f"LLM streaming timed out after {effective_timeout}s"
                        )
                    
                    # Get next chunk with timeout
                    chunk = await asyncio.wait_for(
                        stream_gen.__anext__(),
                        timeout=remaining
                    )
                    chunk_count += 1
                    yield chunk
            except StopAsyncIteration:
                # 🔧 OBSERVABILITY: Log stream completion
                if trace_id:
                    logger.info(f"[trace_id={trace_id}] stream completed ({chunk_count} chunks)")
                return  # Stream completed
            except asyncio.TimeoutError:
                logger.error(f"LLM stream timeout after {effective_timeout}s")
                raise
        
        return _timeout_enforced_stream()

    async def embed(self, texts: list[str], trace_id: str | None = None) -> list[list[float]]:
        """Embed texts with trace_id tracking."""
        if trace_id:
            logger.info(f"[trace_id={trace_id}] embed started for {len(texts)} texts")
        raise NotImplementedError
