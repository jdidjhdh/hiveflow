"""HiveFlow - New Modules Integration Tests

Tests for:
- Checkpoint system
- Streaming utilities
- Human-in-the-loop
- Evaluation framework
- Anthropic client (mock mode)
"""
import asyncio
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import (
    CheckpointManager, MemoryCheckpointBackend, Checkpoint,
    StreamBuffer, StreamEvent, StreamEventType, collect_stream,
    HITLManager, HITLAction, HITLStatus,
    Evaluator, EvaluationReport, BenchmarkSuite, ABTester, EvaluationCriteria,
    MockLLMClient, AnthropicClient,
)


# ======================== Checkpoint Tests ========================

@pytest.mark.asyncio
async def test_checkpoint_save_and_load():
    backend = MemoryCheckpointBackend()
    mgr = CheckpointManager(backend)

    cp_id = await mgr.save_checkpoint(
        workflow_id="wf_001",
        state={"step": 1, "data": "hello"},
        metadata={"description": "After step 1"},
    )
    assert cp_id is not None
    assert len(cp_id) == 12

    cps = await mgr.list_checkpoints("wf_001")
    assert len(cps) == 1
    assert cps[0].state["step"] == 1
    assert cps[0].metadata["description"] == "After step 1"


@pytest.mark.asyncio
async def test_checkpoint_restore():
    backend = MemoryCheckpointBackend()
    mgr = CheckpointManager(backend)

    await mgr.save_checkpoint("wf_001", {"step": 1})
    await mgr.save_checkpoint("wf_001", {"step": 2})

    cps = await mgr.list_checkpoints("wf_001")
    assert len(cps) == 2

    restored = await mgr.restore_checkpoint(cps[0].checkpoint_id)
    assert restored is not None
    assert restored.state["step"] == 1

    current = mgr.get_current_state("wf_001")
    assert current["step"] == 1


@pytest.mark.asyncio
async def test_checkpoint_fork():
    backend = MemoryCheckpointBackend()
    mgr = CheckpointManager(backend)

    cp_id = await mgr.save_checkpoint("wf_001", {"step": 1})
    fork_id = await mgr.fork(cp_id, branch_name="experiment_A")

    assert fork_id is not None
    cps = await mgr.list_checkpoints("wf_001")
    assert len(cps) == 2

    fork_cp = await mgr.load_checkpoint(fork_id) if hasattr(mgr, 'load_checkpoint') else await backend.load(fork_id)
    assert fork_cp is not None
    assert fork_cp.branch_name == "experiment_A"
    assert fork_cp.parent_id == cp_id


@pytest.mark.asyncio
async def test_checkpoint_delete():
    backend = MemoryCheckpointBackend()
    mgr = CheckpointManager(backend)

    cp_id = await mgr.save_checkpoint("wf_001", {"step": 1})
    assert await mgr.delete_checkpoint(cp_id)

    cps = await mgr.list_checkpoints("wf_001")
    assert len(cps) == 0


@pytest.mark.asyncio
async def test_checkpoint_timeline():
    backend = MemoryCheckpointBackend()
    mgr = CheckpointManager(backend)

    cp1 = await mgr.save_checkpoint("wf_001", {"step": 1})
    cp2 = await mgr.save_checkpoint("wf_001", {"step": 2})

    timeline = await mgr.get_checkpoint_timeline("wf_001")
    assert len(timeline) == 2
    assert timeline[0]["state_keys"] == ["step"]


@pytest.mark.asyncio
async def test_checkpoint_multiple_workflows():
    backend = MemoryCheckpointBackend()
    mgr = CheckpointManager(backend)

    await mgr.save_checkpoint("wf_A", {"data": "A"})
    await mgr.save_checkpoint("wf_B", {"data": "B"})

    cps_a = await mgr.list_checkpoints("wf_A")
    cps_b = await mgr.list_checkpoints("wf_B")
    assert len(cps_a) == 1
    assert len(cps_b) == 1
    assert cps_a[0].state["data"] == "A"
    assert cps_b[0].state["data"] == "B"


# ======================== Streaming Tests ========================

@pytest.mark.asyncio
async def test_stream_buffer_put_and_consume():
    buffer = StreamBuffer()

    await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="Hello"))
    await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data=" World"))
    await buffer.close()

    events = []
    async for event in buffer:
        events.append(event)

    assert len(events) == 2
    assert events[0].data == "Hello"
    assert events[1].data == " World"


@pytest.mark.asyncio
async def test_stream_buffer_get_events():
    buffer = StreamBuffer()

    await buffer.put(StreamEvent(type=StreamEventType.NODE_START, data="node_1"))
    await buffer.put(StreamEvent(type=StreamEventType.NODE_END, data="node_1"))

    events = buffer.get_events()
    assert len(events) == 2


@pytest.mark.asyncio
async def test_stream_buffer_close_raises():
    buffer = StreamBuffer()
    await buffer.close()

    with pytest.raises(RuntimeError, match="closed"):
        await buffer.put(StreamEvent(type=StreamEventType.DONE, data={}))


@pytest.mark.asyncio
async def test_collect_stream():
    buffer = StreamBuffer()

    await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="a"))
    await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="b"))
    await buffer.put(StreamEvent(type=StreamEventType.DONE, data="done"))
    await buffer.close()

    events = await collect_stream(buffer)
    assert len(events) == 3


@pytest.mark.asyncio
async def test_stream_event_sse_format():
    event = StreamEvent(
        type=StreamEventType.TOKEN,
        data="Hello",
        node_id="node_1",
    )
    sse = event.to_sse()
    assert "event: token" in sse
    assert 'data: "Hello"' in sse
    assert "id: node_1" in sse


@pytest.mark.asyncio
async def test_stream_event_json_format():
    event = StreamEvent(
        type=StreamEventType.TOOL_CALL,
        data={"tool": "search", "query": "test"},
        workflow_id="wf_001",
    )
    json_str = event.to_json()
    import json
    parsed = json.loads(json_str)
    assert parsed["type"] == "tool_call"
    assert parsed["workflow_id"] == "wf_001"
    assert parsed["data"]["tool"] == "search"


# ======================== HITL Tests ========================

@pytest.mark.asyncio
async def test_hitl_create_and_respond():
    mgr = HITLManager()

    gate = await mgr.create_gate(
        workflow_id="wf_001",
        node_id="review",
        action=HITLAction.APPROVAL,
        prompt="Approve this output?",
        context={"output": "Generated text"},
    )

    assert gate.status == HITLStatus.PENDING
    assert gate.gate_id is not None

    result = await mgr.respond(gate.gate_id, approved=True, comment="Looks good!")
    assert result.status == HITLStatus.APPROVED
    assert result.human_comment == "Looks good!"


@pytest.mark.asyncio
async def test_hitl_reject():
    mgr = HITLManager()

    gate = await mgr.create_gate(
        workflow_id="wf_001",
        node_id="review",
        action=HITLAction.APPROVAL,
        prompt="Approve?",
    )

    await mgr.respond(gate.gate_id, approved=False, comment="Not good enough")
    gate = await mgr.get_gate(gate.gate_id)
    assert gate.status == HITLStatus.REJECTED


@pytest.mark.asyncio
async def test_hitl_review_and_modify():
    mgr = HITLManager()

    gate = await mgr.create_gate(
        workflow_id="wf_001",
        node_id="edit",
        action=HITLAction.REVIEW,
        prompt="Review and modify",
        context={"draft": "Original draft"},
    )

    await mgr.respond(
        gate.gate_id,
        modified_data="Revised draft",
        comment="Improved the language",
    )
    gate = await mgr.get_gate(gate.gate_id)
    assert gate.status == HITLStatus.MODIFIED
    assert gate.human_response == "Revised draft"


@pytest.mark.asyncio
async def test_hitl_input():
    mgr = HITLManager()

    gate = await mgr.create_gate(
        workflow_id="wf_001",
        node_id="ask_user",
        action=HITLAction.INPUT,
        prompt="What topic should I cover?",
    )

    await mgr.respond(
        gate.gate_id,
        input_data="Machine Learning basics",
    )
    gate = await mgr.get_gate(gate.gate_id)
    assert gate.status == HITLStatus.APPROVED
    assert gate.human_response == "Machine Learning basics"


@pytest.mark.asyncio
async def test_hitl_wait_for_response_timeout():
    mgr = HITLManager()

    gate = await mgr.create_gate(
        workflow_id="wf_001",
        node_id="review",
        action=HITLAction.APPROVAL,
        prompt="Approve?",
        timeout_seconds=0.1,
        on_timeout="fail",
    )

    result = await mgr.wait_for_response(gate.gate_id)
    assert result.status == HITLStatus.TIMED_OUT


@pytest.mark.asyncio
async def test_hitl_timeout_approve():
    mgr = HITLManager()

    gate = await mgr.create_gate(
        workflow_id="wf_001",
        node_id="review",
        action=HITLAction.APPROVAL,
        prompt="Approve?",
        timeout_seconds=0.1,
        on_timeout="approve",
    )

    result = await mgr.wait_for_response(gate.gate_id)
    assert result.status == HITLStatus.APPROVED
    assert "timeout" in result.human_comment.lower()


@pytest.mark.asyncio
async def test_hitl_list_pending_gates():
    mgr = HITLManager()

    await mgr.create_gate("wf_001", "node1", HITLAction.APPROVAL, "Approve 1?")
    await mgr.create_gate("wf_001", "node2", HITLAction.APPROVAL, "Approve 2?")
    await mgr.create_gate("wf_002", "node3", HITLAction.APPROVAL, "Approve 3?")

    pending = await mgr.list_pending_gates()
    assert len(pending) == 3

    pending_wf1 = await mgr.list_pending_gates(workflow_id="wf_001")
    assert len(pending_wf1) == 2


@pytest.mark.asyncio
async def test_hitl_cancel_gate():
    mgr = HITLManager()

    gate = await mgr.create_gate("wf_001", "node1", HITLAction.APPROVAL, "Approve?")
    assert await mgr.cancel_gate(gate.gate_id)

    gate = await mgr.get_gate(gate.gate_id)
    assert gate.status == HITLStatus.CANCELLED


@pytest.mark.asyncio
async def test_hitl_stats():
    mgr = HITLManager()

    g1 = await mgr.create_gate("wf_001", "n1", HITLAction.APPROVAL, "Q1?")
    g2 = await mgr.create_gate("wf_001", "n2", HITLAction.APPROVAL, "Q2?")
    g3 = await mgr.create_gate("wf_001", "n3", HITLAction.APPROVAL, "Q3?")

    await mgr.respond(g1.gate_id, approved=True)
    await mgr.respond(g2.gate_id, approved=False)
    # g3 still pending

    stats = mgr.get_gate_stats()
    assert stats["total"] == 3
    assert stats["approved"] == 1
    assert stats["rejected"] == 1
    assert stats["pending"] == 1
    assert stats["approval_rate"] == 0.5


@pytest.mark.asyncio
async def test_hitl_respond_nonexistent_gate():
    mgr = HITLManager()
    result = await mgr.respond("nonexistent", approved=True)
    assert result is None


@pytest.mark.asyncio
async def test_hitl_double_respond():
    mgr = HITLManager()
    gate = await mgr.create_gate("wf_001", "n1", HITLAction.APPROVAL, "Q?")
    await mgr.respond(gate.gate_id, approved=True)
    result = await mgr.respond(gate.gate_id, approved=False)
    # Second respond should return existing gate without changing status
    assert result.status == HITLStatus.APPROVED


# ======================== Evaluation Tests ========================

@pytest.mark.asyncio
async def test_evaluator_basic_criteria():
    evaluator = Evaluator()
    evaluator.add_criteria("accuracy", "Is output correct?")
    evaluator.add_criteria("completeness", "Does output address all requirements?")

    assert "accuracy" in evaluator.criteria
    assert "completeness" in evaluator.criteria


@pytest.mark.asyncio
async def test_evaluator_custom_evaluator():
    evaluator = Evaluator()

    def length_check(input_text, output_text, expected, context):
        return min(len(output_text) / 100, 1.0), "length check"

    evaluator.add_custom_evaluator("length", length_check)

    report = await evaluator.evaluate(
        workflow_id="wf_001",
        test_name="test",
        input_text="hello",
        output_text="A" * 50,
    )
    assert report.total_score > 0
    assert len(report.results) == 1


@pytest.mark.asyncio
async def test_evaluation_report():
    report = EvaluationReport(
        workflow_id="wf_001",
        test_name="test",
        total_score=0.85,
        passed=True,
    )
    assert report.workflow_id == "wf_001"
    assert report.total_score == 0.85
    assert report.passed


@pytest.mark.asyncio
async def test_evaluator_weighted_scoring():
    evaluator = Evaluator()
    evaluator.add_criteria("accuracy", "Is it correct?", weight=2.0, threshold=0.8)
    evaluator.add_criteria("style", "Is it well written?", weight=1.0, threshold=0.5)

    evaluator.add_custom_evaluator("accuracy", lambda *a: (0.9, "accurate"))
    evaluator.add_custom_evaluator("style", lambda *a: (0.6, "decent"))

    report = await evaluator.evaluate(
        workflow_id="wf_001",
        test_name="weighted_test",
        input_text="",
        output_text="",
    )

    # accuracy: 0.9 * 2.0 = 1.8, style: 0.6 * 1.0 = 0.6, total = 2.4 / 3.0 = 0.8
    assert abs(report.total_score - 0.8) < 0.01


@pytest.mark.asyncio
async def test_evaluator_llm_mode(mock_llm_client):
    evaluator = Evaluator(llm_client=mock_llm_client, model="gpt-4")
    evaluator.add_criteria("quality", "Overall quality")

    # Mock response should return valid JSON
    report = await evaluator.evaluate(
        workflow_id="wf_001",
        test_name="llm_test",
        input_text="Summarize this",
        output_text="A brief summary",
        expected_output="Expected summary",
    )
    assert report.workflow_id == "wf_001"
    assert isinstance(report.total_score, float)


@pytest.fixture
def mock_llm_client():
    return MockLLMClient(response='{"score": 0.8, "reason": "good output"}')


# ======================== Benchmark Suite Tests ========================

@pytest.mark.asyncio
async def test_benchmark_suite():
    suite = BenchmarkSuite("my_benchmark")
    suite.add_test(
        name="test1",
        input_text="Summarize this text",
        expected_output="A brief summary",
    )
    suite.add_test(
        name="test2",
        input_text="Translate to French",
        expected_output="Bonjour le monde",
    )

    evaluator = Evaluator()
    evaluator.add_custom_evaluator("quality", lambda *a: (0.8, "good"))

    async def agent_fn(input_text):
        return f"Response to: {input_text}"

    reports = await suite.run(evaluator, agent_fn)
    assert len(reports) == 2


@pytest.mark.asyncio
async def test_benchmark_summary():
    suite = BenchmarkSuite("summary_test")
    suite.add_test("t1", "input1", "expected_output1")

    evaluator = Evaluator()
    evaluator.add_custom_evaluator("quality", lambda *a: (0.9, "good"))

    async def agent_fn(text):
        return text

    reports = await suite.run(evaluator, agent_fn)
    summary = suite.summary(reports)
    assert summary["tests"] == 1
    assert summary["avg_score"] > 0


# ======================== A/B Testing ========================

@pytest.mark.asyncio
async def test_ab_tester():
    evaluator = Evaluator()
    evaluator.add_custom_evaluator("quality", lambda *a: (0.85, "good"))

    async def agent_a(text):
        return f"A: {text}"

    async def agent_b(text):
        return f"B: {text}"

    tester = ABTester(evaluator)
    results = await tester.compare(
        input_text="Test input",
        agent_a_fn=agent_a,
        agent_b_fn=agent_b,
        test_name="ab_test",
    )

    assert "A" in results
    assert "B" in results
    assert "winner" in results
    assert "score_diff" in results


# ======================== Anthropic Client Tests ========================

def test_anthropic_client_import():
    """Test that AnthropicClient class exists."""
    assert AnthropicClient is not None


def test_anthropic_message_conversion():
    """Test message conversion logic."""
    from hiveflow import LLMMessage

    messages = [
        LLMMessage(role="system", content="You are helpful"),
        LLMMessage(role="user", content="Hello"),
        LLMMessage(role="assistant", content="Hi there"),
    ]

    system, chat = AnthropicClient._to_anthropic_messages(messages)
    assert system == "You are helpful"
    assert len(chat) == 2
    assert chat[0]["role"] == "user"
    assert chat[1]["role"] == "assistant"


def test_anthropic_tool_conversion():
    """Test tool definition conversion."""
    from hiveflow import LLMToolDefinition

    tools = [
        LLMToolDefinition(
            name="search",
            description="Search the web",
            parameters={"type": "object", "properties": {"query": {"type": "string"}}},
        ),
    ]

    converted = AnthropicClient._to_tool_defs(tools)
    assert len(converted) == 1
    assert converted[0]["name"] == "search"
    assert converted[0]["input_schema"]["type"] == "object"
