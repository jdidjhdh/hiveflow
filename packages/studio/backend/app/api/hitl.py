"""HiveFlow Studio - Human-in-the-Loop (HITL) API"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.engine_service import get_engine
from hiveflow import HITLStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hitl", tags=["hitl"])


class HITLRespondRequest(BaseModel):
    approved: bool = True
    comment: str = ""
    modified_data: Optional[Any] = None
    input_data: Optional[Any] = None


def _serialize_gate(gate) -> dict:
    return {
        "gate_id": gate.gate_id,
        "workflow_id": gate.workflow_id,
        "node_id": gate.node_id,
        "action": gate.action.value,
        "prompt": gate.prompt,
        "context": gate.context,
        "status": gate.status.value,
        "human_response": gate.human_response,
        "human_comment": gate.human_comment,
        "created_at": gate.created_at,
        "responded_at": gate.responded_at,
        "timeout_seconds": gate.timeout_seconds,
        "on_timeout": gate.on_timeout,
    }


@router.get("/pending")
async def list_pending_gates(workflow_id: Optional[str] = None):
    """List pending approval gates."""
    engine = get_engine()
    mgr = engine.get_hitl_manager()
    gates = await mgr.list_pending_gates(workflow_id)
    return {"gates": [_serialize_gate(g) for g in gates]}


@router.get("/stats")
async def hitl_stats():
    engine = get_engine()
    return engine.get_hitl_manager().get_gate_stats()


@router.get("/{gate_id}")
async def get_gate(gate_id: str):
    engine = get_engine()
    gate = await engine.get_hitl_manager().get_gate(gate_id)
    if not gate:
        raise HTTPException(status_code=404, detail=f"HITL gate '{gate_id}' not found")
    return _serialize_gate(gate)


@router.post("/{gate_id}/respond")
async def respond_to_gate(gate_id: str, body: HITLRespondRequest):
    """Approve, reject, or provide input for a pending gate."""
    engine = get_engine()
    mgr = engine.get_hitl_manager()
    gate = await mgr.respond(
        gate_id,
        approved=body.approved,
        modified_data=body.modified_data,
        comment=body.comment,
        input_data=body.input_data,
    )
    if gate is None:
        raise HTTPException(status_code=404, detail=f"HITL gate '{gate_id}' not found")
    return _serialize_gate(gate)


@router.post("/{gate_id}/cancel")
async def cancel_gate(gate_id: str):
    engine = get_engine()
    ok = await engine.get_hitl_manager().cancel_gate(gate_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Pending gate '{gate_id}' not found")
    gate = await engine.get_hitl_manager().get_gate(gate_id)
    return _serialize_gate(gate) if gate else {"gate_id": gate_id, "status": HITLStatus.CANCELLED.value}
