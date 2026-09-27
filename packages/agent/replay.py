"""Replay debugger from SecureBlackboard audit log and checkpoints."""
import time
from typing import Any

try:
    from hiveflow.observability.failure_reason import FailureReason, infer_failure_reason
except ImportError:
    from observability.failure_reason import FailureReason, infer_failure_reason  # type: ignore


def merge_timeline_entries(
    *,
    intent_events: list[dict[str, Any]],
    node_events: list[dict[str, Any]],
    audit_events: list[dict[str, Any]],
    hitl_events: list[dict[str, Any]],
    bus_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Merge heterogeneous execution records into a single sorted timeline."""
    entries: list[dict[str, Any]] = []

    for e in intent_events:
        intent_type = e.get("intent", "")
        payload = e.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {"value": payload}
        status = e.get("status", "")

        if intent_type == "hitl.decision":
            explicit = payload.get("failure_reason")
            failure_reason = explicit if status in ("failed", "rejected") and explicit else None
            if failure_reason is None and status in ("rejected", "cancelled"):
                failure_reason = FailureReason.HITL_REJECTED.value
            entries.append({
                "kind": "hitl",
                "timestamp": e.get("timestamp"),
                "status": status,
                "action": "decision",
                "gate_id": payload.get("gate_id"),
                "node_id": payload.get("node_id"),
                "emitter": e.get("emitter") or payload.get("actor"),
                "actor": payload.get("actor") or e.get("emitter"),
                "human_comment": payload.get("human_comment"),
                "comment_template": payload.get("comment_template"),
                "prompt": payload.get("action"),
                "payload": payload,
                "failure_reason": failure_reason,
            })
            continue

        explicit = payload.get("failure_reason")
        failure_reason = explicit if status in ("failed", "timeout") and explicit else None
        if failure_reason is None and status in ("failed", "timeout"):
            failure_reason = infer_failure_reason(
                status=status,
                intent=intent_type,
                payload=payload,
            ).value
        entries.append({
            "kind": "plan",
            "timestamp": e.get("timestamp"),
            "status": status,
            "intent": intent_type,
            "emitter": e.get("emitter"),
            "payload": payload if isinstance(payload, dict) else {},
            "failure_reason": failure_reason,
        })

    for e in node_events:
        entries.append({
            "kind": "node",
            "timestamp": e.get("timestamp"),
            "status": "completed",
            "node_name": e.get("node_name"),
            "node_id": e.get("node_name"),
            "duration_ms": e.get("duration_ms"),
            "emitter": "workflow",
        })

    for e in audit_events:
        entries.append({
            "kind": "blackboard",
            "timestamp": e.get("timestamp"),
            "status": "completed",
            "action": e.get("action"),
            "agent": e.get("agent"),
            "key": e.get("key"),
            "emitter": e.get("agent"),
        })

    for g in hitl_events:
        status = g.get("status", "pending")
        if status in ("rejected", "cancelled"):
            failure_reason = FailureReason.HITL_REJECTED.value
        elif status == "timed_out":
            failure_reason = FailureReason.TIMEOUT.value
        else:
            failure_reason = None
        entries.append({
            "kind": "hitl",
            "timestamp": g.get("created_at") or g.get("timestamp"),
            "status": status,
            "gate_id": g.get("gate_id"),
            "node_id": g.get("node_id"),
            "action": g.get("action"),
            "prompt": g.get("prompt"),
            "emitter": g.get("workflow_id"),
            "failure_reason": failure_reason,
        })
        responded_at = g.get("responded_at")
        if responded_at and responded_at != g.get("created_at"):
            entries.append({
                "kind": "hitl",
                "timestamp": responded_at,
                "status": status,
                "gate_id": g.get("gate_id"),
                "node_id": g.get("node_id"),
                "action": f"{g.get('action', 'hitl')}_response",
                "emitter": g.get("actor") or "human",
                "actor": g.get("actor"),
                "human_comment": g.get("human_comment"),
                "comment_template": g.get("comment_template"),
                "prompt": g.get("prompt"),
            })

    for e in bus_events or []:
        topic = e.get("topic", "")
        payload = e.get("payload") or e.get("data") or {}
        if not isinstance(payload, dict):
            payload = {"value": payload}
        kind = "task"
        status = "running"
        if topic.startswith("hitl."):
            kind = "hitl"
            status = topic.split(".", 1)[-1]
        elif topic.startswith("workflow."):
            kind = "node" if "checkpoint" not in topic else "checkpoint"
            status = "failed" if "failed" in topic else "completed" if "completed" in topic else "running"
        elif "tool" in topic or "mcp" in topic:
            kind = "tool"
            status = "failed" if "failed" in topic else "completed" if "completed" in topic else "running"
        else:
            status = "failed" if "failed" in topic else "completed" if "completed" in topic else "running"
        if "timeout" in topic:
            status = "timeout"
        explicit = payload.get("failure_reason") or e.get("failure_reason")
        failure_reason = explicit
        if failure_reason is None and status in ("failed", "timeout"):
            failure_reason = infer_failure_reason(
                status=status,
                intent=topic,
                payload=payload,
            ).value
        entries.append({
            "kind": kind,
            "timestamp": e.get("timestamp"),
            "status": status,
            "topic": topic,
            "intent": topic,
            "emitter": payload.get("actor") or payload.get("emitter") or payload.get("node_id"),
            "actor": payload.get("actor"),
            "human_comment": payload.get("comment") or payload.get("human_comment"),
            "comment_template": payload.get("template_id") or payload.get("comment_template"),
            "gate_id": payload.get("gate_id"),
            "node_id": payload.get("node_id"),
            "payload": payload,
            "failure_reason": failure_reason,
        })

    entries.sort(key=lambda x: x.get("timestamp") or 0)
    return entries


def summarize_timeline(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive run status, failed step, reason, and blackboard keys touched."""
    if not entries:
        return {
            "status": "unknown",
            "failed_step": None,
            "failure_reason": None,
            "blackboard_keys": [],
            "entry_count": 0,
        }

    terminal_status = "completed"
    failed_step = None
    failure_reason = None

    for e in reversed(entries):
        st = e.get("status", "")
        if st in ("failed", "rejected", "cancelled", "timed_out", "timeout"):
            terminal_status = "failed"
            failed_step = (
                e.get("node_name")
                or e.get("node_id")
                or e.get("intent")
                or e.get("topic")
                or e.get("kind")
            )
            failure_reason = e.get("failure_reason") or infer_failure_reason(
                status=st,
                intent=e.get("intent", "") or e.get("topic", ""),
                payload=e.get("payload") if isinstance(e.get("payload"), dict) else {},
                hitl_status=st,
            ).value
            break
        if st == "timeout":
            terminal_status = "failed"
            failure_reason = FailureReason.TIMEOUT.value
            break

    if terminal_status != "failed":
        pending = any(e.get("status") == "pending" for e in entries)
        terminal_status = "running" if pending else "completed"

    keys = sorted({
        e.get("key")
        for e in entries
        if e.get("kind") == "blackboard" and e.get("key")
    })

    return {
        "status": terminal_status,
        "failed_step": failed_step,
        "failure_reason": failure_reason,
        "blackboard_keys": keys,
        "entry_count": len(entries),
    }


class ReplayDebugger:
    """Inspect past runs via blackboard audit entries and optional checkpoints."""

    def __init__(self, blackboard, checkpoint_manager=None):
        self._blackboard = blackboard
        self._checkpoints = checkpoint_manager

    def get_audit_timeline(
        self,
        *,
        agent: str = "",
        key: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        audit = getattr(self._blackboard, "_audit_log", [])
        rows = list(audit)
        if agent:
            rows = [e for e in rows if e.get("agent") == agent]
        if key:
            rows = [e for e in rows if e.get("key") == key]
        return rows[-limit:]

    async def get_checkpoint_timeline(self, workflow_id: str) -> list[dict[str, Any]]:
        if not self._checkpoints:
            return []
        return await self._checkpoints.get_checkpoint_timeline(workflow_id)

    def build_replay_session(
        self,
        intent_id: str,
        *,
        limit: int = 200,
    ) -> dict[str, Any]:
        prefix = f"hiveflow:result:{intent_id}"
        audit = self.get_audit_timeline(key="", limit=limit)
        related = [
            e for e in audit
            if e.get("key", "").startswith(prefix) or intent_id in e.get("key", "")
        ]
        return {
            "intent_id": intent_id,
            "events": related,
            "event_count": len(related),
            "exported_at": time.time(),
        }
