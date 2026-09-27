"""Tests for unified timeline merge helpers."""
from replay import merge_timeline_entries, summarize_timeline


def test_merge_timeline_orders_by_timestamp():
    entries = merge_timeline_entries(
        intent_events=[
            {"timestamp": 2.0, "status": "completed", "intent": "agent_query", "emitter": "studio"},
        ],
        node_events=[
            {"timestamp": 1.0, "node_name": "research", "duration_ms": 50.0},
        ],
        audit_events=[
            {"timestamp": 3.0, "action": "put", "agent": "worker", "key": "hiveflow:result:x"},
        ],
        hitl_events=[],
        bus_events=[],
    )
    assert len(entries) == 3
    assert entries[0]["kind"] == "node"
    assert entries[1]["kind"] == "plan"
    assert entries[2]["kind"] == "blackboard"


def test_summarize_timeline_detects_failure():
    entries = merge_timeline_entries(
        intent_events=[
            {"timestamp": 1.0, "status": "completed", "intent": "plan", "emitter": "studio"},
            {
                "timestamp": 2.0,
                "status": "failed",
                "intent": "task.failed",
                "emitter": "worker-1",
                "payload": {
                    "failure_reason": "tool_error",
                    "error": "MCP tool timeout",
                },
            },
        ],
        node_events=[],
        audit_events=[],
        hitl_events=[],
        bus_events=[],
    )
    summary = summarize_timeline(entries)
    assert summary["status"] == "failed"
    assert summary["failure_reason"] == "tool_error"


def test_summarize_timeline_explicit_hitl_rejected():
    entries = merge_timeline_entries(
        intent_events=[],
        node_events=[],
        audit_events=[],
        hitl_events=[
            {
                "gate_id": "g1",
                "node_id": "review",
                "action": "approval",
                "status": "rejected",
                "created_at": 1.0,
            },
        ],
        bus_events=[],
    )
    summary = summarize_timeline(entries)
    assert summary["status"] == "failed"
    assert summary["failure_reason"] == "hitl_rejected"
