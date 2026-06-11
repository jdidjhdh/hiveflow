"""Replay debugger API — audit timeline from real blackboard."""
from fastapi import APIRouter, HTTPException

from app.core.engine_service import get_engine

router = APIRouter(prefix="/replay", tags=["replay"])


@router.get("/audit")
async def replay_audit(intent_id: str = "", agent: str = "", key: str = "", limit: int = 100):
    engine = get_engine()
    debugger = engine.get_replay_debugger()
    if intent_id:
        return debugger.build_replay_session(intent_id, limit=limit)
    return {
        "events": debugger.get_audit_timeline(agent=agent, key=key, limit=limit),
        "event_count": len(debugger.get_audit_timeline(agent=agent, key=key, limit=limit)),
    }


@router.get("/checkpoints/{workflow_id}")
async def replay_checkpoints(workflow_id: str):
    engine = get_engine()
    debugger = engine.get_replay_debugger()
    timeline = await debugger.get_checkpoint_timeline(workflow_id)
    return {"workflow_id": workflow_id, "checkpoints": timeline}
