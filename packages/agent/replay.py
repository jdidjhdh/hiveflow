"""Replay debugger from SecureBlackboard audit log and checkpoints."""
import time
from typing import Any, Dict, List, Optional


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
    ) -> List[Dict[str, Any]]:
        audit = getattr(self._blackboard, "_audit_log", [])
        rows = list(audit)
        if agent:
            rows = [e for e in rows if e.get("agent") == agent]
        if key:
            rows = [e for e in rows if e.get("key") == key]
        return rows[-limit:]

    async def get_checkpoint_timeline(self, workflow_id: str) -> List[Dict[str, Any]]:
        if not self._checkpoints:
            return []
        return await self._checkpoints.get_checkpoint_timeline(workflow_id)

    def build_replay_session(
        self,
        intent_id: str,
        *,
        limit: int = 200,
    ) -> Dict[str, Any]:
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
