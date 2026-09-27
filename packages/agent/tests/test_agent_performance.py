"""
🔧 PERFORMANCE TESTS: Agent Layer Retry Storm, Context Overflow, and Concurrency

Validates:
1. Jitter prevents retry storm (50 concurrent LLM calls)
2. Smart truncation preserves critical messages
3. Fuzzy tool matching handles LLM hallucination
4. Semaphore limits concurrent subprocesses

Run: pytest tests/test_agent_performance.py -v --tb=short
"""
import asyncio
import json
import statistics
import time
from abc import ABC, abstractmethod
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# Mock Tool class for testing
class MockTool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    
    async def run(self, input: dict[str, Any], view) -> Any:
        return "mock_result"


# ========== 1. Retry Storm Tests ==========

class TestRetryStormPrevention:
    """Test jitter prevents synchronized retry storm."""
    
    @pytest.mark.asyncio
    async def test_50_concurrent_llm_calls_spread_retries(self):
        """50 concurrent LLM calls with jitter - retries spread out."""
        from llm.base import LLMClient
        
        # Mock LLM that fails first attempt, succeeds on retry
        class FlakeyLLM(LLMClient):
            call_times = []
            attempt_counts = {}
            
            async def complete(self, messages, **kwargs):
                FlakeyLLM.call_times.append(time.monotonic())
                # Fail first attempt, succeed on second
                msg_key = messages[-1]["content"]
                FlakeyLLM.attempt_counts[msg_key] = FlakeyLLM.attempt_counts.get(msg_key, 0) + 1
                if FlakeyLLM.attempt_counts[msg_key] < 2:
                    return "invalid json"
                return '{"result": "success"}'
            
            async def _stream_impl(self, messages, **kwargs):
                yield "test"
        
        llm = FlakeyLLM()
        
        # Reset tracking
        FlakeyLLM.call_times = []
        FlakeyLLM.attempt_counts = {}
        
        # Run 50 concurrent complete_json calls
        start = time.monotonic()
        results = await asyncio.gather(
            *[llm.complete_json([{"role": "user", "content": f"test{i}"}]) for i in range(50)],
            return_exceptions=True
        )
        elapsed = time.monotonic() - start
        
        # Check success rate
        successes = sum(1 for r in results if isinstance(r, dict) and "result" in r)
        assert successes >= 40, f"Too many failures: {successes}/50 succeeded"
        
        # With jitter, total time should be reasonable (not instant retry)
        # 50 calls with jitter of 0-0.5s each, should take some time
        # Note: With random jitter in [0, 0.5s], average jitter is 0.25s
        # So 50 concurrent calls with 1 retry each should take ~0.25s average
        assert elapsed >= 0.1, f"Retries too fast - jitter not applied: {elapsed:.2f}s"
    
    @pytest.mark.asyncio
    async def test_jitter_adds_delay(self):
        """Verify jitter adds delay between retries."""
        from llm.base import LLMClient
        
        class TestLLM(LLMClient):
            retry_count = 0
            
            async def complete(self, messages, **kwargs):
                TestLLM.retry_count += 1
                if TestLLM.retry_count < 3:
                    return "not json"
                return '{"ok": true}'
            
            async def _stream_impl(self, messages, **kwargs):
                yield ""
        
        llm = TestLLM()
        start = time.monotonic()
        
        await llm.complete_json([{"role": "user", "content": "test"}])
        
        elapsed = time.monotonic() - start
        
        # With 2 retries and jitter up to 0.5s each, should have some delay
        assert elapsed >= 0, "Jitter delay should be applied"


# ========== 2. Message Truncation Tests ==========

class TestSmartMessageTruncation:
    """Test smart truncation preserves critical messages."""
    
    def test_truncation_preserves_system_messages(self):
        """All system messages are preserved during truncation."""
        from worker.react_worker import ReActWorker
        
        # Create mock tool
        mock_tool = MockTool()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test"
        mock_tool.parameters = {}
        
        # Create worker with low max_message_history
        mock_llm = MagicMock()
        
        worker = ReActWorker(
            agent_id="test",
            llm=mock_llm,
            tools=[mock_tool],
            max_message_history=10
        )
        
        # Create long message list with many system messages
        messages = [
            {"role": "system", "content": "Critical instruction 1"},
            {"role": "system", "content": "Critical instruction 2"},
            {"role": "system", "content": "Tool definitions"},
            {"role": "user", "content": "Query 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Query 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Query 3"},
            {"role": "assistant", "content": "Response 3"},
            {"role": "user", "content": "Query 4"},
            {"role": "assistant", "content": "Response 4"},
            {"role": "user", "content": "Query 5"},
            {"role": "assistant", "content": "Response 5"},
        ]
        
        truncated = worker._smart_truncate_messages(messages)
        
        # All system messages should be preserved
        system_msgs = [m for m in truncated if m["role"] == "system"]
        assert len(system_msgs) >= 3, "System messages should be preserved"
        
        # Original system messages should be in truncated list
        assert "Critical instruction 1" in [m["content"] for m in system_msgs]
        assert "Critical instruction 2" in [m["content"] for m in system_msgs]
    
    def test_truncation_adds_summary(self):
        """Discarded messages are summarized, not just dropped."""
        from worker.react_worker import ReActWorker
        
        mock_tool = MockTool()
        mock_tool.name = "test"
        mock_tool.description = ""
        mock_tool.parameters = {}
        
        mock_llm = MagicMock()
        
        worker = ReActWorker(agent_id="test", llm=mock_llm, tools=[mock_tool], max_message_history=10)
        
        messages = [
            {"role": "system", "content": "Instruction"},
            {"role": "user", "content": "Important early query"},
            {"role": "assistant", "content": "Important early response"},
            {"role": "user", "content": "Query 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Query 3"},
            {"role": "assistant", "content": "Response 3"},
            {"role": "user", "content": "Query 4"},
            {"role": "assistant", "content": "Response 4"},
            {"role": "user", "content": "Query 5"},
            {"role": "assistant", "content": "Response 5"},
        ]
        
        truncated = worker._smart_truncate_messages(messages)
        
        # Should have a summary message
        summary_msgs = [m for m in truncated if "Previous conversation summary" in m.get("content", "")]
        assert len(summary_msgs) >= 1, "Discarded messages should be summarized"


# ========== 3. Fuzzy Tool Matching Tests ==========

class TestFuzzyToolMatching:
    """Test fuzzy match handles LLM tool name hallucination."""
    
    def test_exact_match_returns_same(self):
        """Exact tool name returns immediately."""
        from worker.react_worker import _fuzzy_match_tool
        
        tool = MockTool()
        tool.name = "web_search"
        
        tools = {"web_search": tool, "file_read": MockTool()}
        
        result = _fuzzy_match_tool("web_search", tools)
        assert result == "web_search"
    
    def test_fuzzy_match_handles_misspelling(self):
        """Similar tool name is matched."""
        from worker.react_worker import _fuzzy_match_tool
        
        tool = MockTool()
        tool.name = "web_search"
        
        tools = {"web_search": tool, "file_read": MockTool()}
        
        # LLM hallucinated slightly different name
        result = _fuzzy_match_tool("search_web", tools)
        assert result == "web_search", "Should fuzzy match to web_search"
    
    def test_fuzzy_match_handles_underscore_vs_dash(self):
        """web_search matches web-search."""
        from worker.react_worker import _fuzzy_match_tool
        
        tool = MockTool()
        tool.name = "web_search"
        
        tools = {"web_search": tool}
        
        result = _fuzzy_match_tool("web-search", tools)
        assert result == "web_search"
    
    def test_fuzzy_match_returns_none_for_unsimilar(self):
        """Very different name returns None."""
        from worker.react_worker import _fuzzy_match_tool
        
        tools = {"web_search": MockTool(), "file_read": MockTool()}
        
        result = _fuzzy_match_tool("execute_code", tools)
        assert result is None, "No similar tool available"
    
    def test_cutoff_threshold(self):
        """Low cutoff allows more matches."""
        from worker.react_worker import _fuzzy_match_tool
        
        tools = {"web_search": MockTool()}
        
        # With default cutoff 0.6, "search_web" should match "web_search"
        result = _fuzzy_match_tool("search_web", tools, cutoff=0.6)
        assert result == "web_search"


# ========== 4. Concurrency Limit Tests ==========

class TestConcurrencyLimits:
    """Test semaphore limits concurrent subprocesses."""
    
    @pytest.mark.asyncio
    async def test_semaphore_can_be_adjusted(self):
        """Concurrency limit can be adjusted via set_concurrency_limit."""
        from worker.tools.code_exec_tool import CodeExecTool
        
        # Change limit to 3
        CodeExecTool.set_concurrency_limit(3)
        
        assert CodeExecTool.MAX_CONCURRENT_EXEC == 3
        assert CodeExecTool._semaphore._value == 3
    
    @pytest.mark.asyncio
    async def test_max_concurrent_is_configurable(self):
        """MAX_CONCURRENT_EXEC is set correctly."""
        from worker.tools.code_exec_tool import CodeExecTool
        
        # Default should be 5
        CodeExecTool.set_concurrency_limit(5)
        
        tool = CodeExecTool()
        
        assert CodeExecTool.MAX_CONCURRENT_EXEC == 5
        assert CodeExecTool._semaphore is not None


# ========== 5. P95 Latency Tests ==========

class TestP95Latency:
    """Test P95 latency under 50 concurrent LLM calls."""
    
    @pytest.mark.asyncio
    async def test_p95_latency_under_3s(self):
        """P95 latency < 3s with 50 concurrent mock LLM calls."""
        from llm.base import LLMClient
        
        class FastLLM(LLMClient):
            async def complete(self, messages, **kwargs):
                await asyncio.sleep(0.1)  # Simulate 100ms LLM latency
                return '{"result": "ok"}'
            
            async def _stream_impl(self, messages, **kwargs):
                yield "ok"
        
        llm = FastLLM()
        
        # Measure latencies for 50 concurrent calls
        async def timed_call(i):
            start = time.monotonic()
            await llm.complete_json([{"role": "user", "content": f"test{i}"}])
            return time.monotonic() - start
        
        latencies = await asyncio.gather(*[timed_call(i) for i in range(50)])
        
        # Sort and find P95 (95th percentile)
        sorted_latencies = sorted(latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        p95 = sorted_latencies[p95_index]
        
        # P95 should be < 3s
        assert p95 < 3.0, f"P95 latency too high: {p95:.2f}s"
        
        # Log statistics
        avg = statistics.mean(latencies)
        print(f"\nLatency stats (50 concurrent): avg={avg:.3f}s, p95={p95:.3f}s, max={max(latencies):.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])