"""HiveFlow Studio - Workflow checkpoint API"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.core.engine_service import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/checkpoints", tags=["checkpoints"])


@router.get("/{workflow_id}")
async def list_checkpoints(workflow_id: str):
    engine = get_engine()
    mgr = engine.get_checkpoint_manager()
    cps = await mgr.list_checkpoints(workflow_id)
    return {
        "workflow_id": workflow_id,
        "checkpoints": [
            {
                "checkpoint_id": cp.checkpoint_id,
                "timestamp": cp.timestamp,
                "metadata": cp.metadata,
                "parent_id": cp.parent_id,
                "branch_name": cp.branch_name,
            }
            for cp in cps
        ],
    }


@router.get("/detail/{checkpoint_id}")
async def get_checkpoint(checkpoint_id: str):
    engine = get_engine()
    mgr = engine.get_checkpoint_manager()
    cp = await mgr.restore_checkpoint(checkpoint_id)
    if not cp:
        raise HTTPException(status_code=404, detail=f"Checkpoint '{checkpoint_id}' not found")
    return {
        "checkpoint_id": cp.checkpoint_id,
        "workflow_id": cp.workflow_id,
        "timestamp": cp.timestamp,
        "state": cp.state,
        "metadata": cp.metadata,
        "parent_id": cp.parent_id,
        "branch_name": cp.branch_name,
    }


@router.post("/{workflow_id}/fork/{checkpoint_id}")
async def fork_checkpoint(workflow_id: str, checkpoint_id: str, branch_name: Optional[str] = None):
    engine = get_engine()
    mgr = engine.get_checkpoint_manager()
    fork_id = await mgr.fork(checkpoint_id, branch_name or f"branch_{checkpoint_id[:8]}")
    if not fork_id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return {"workflow_id": workflow_id, "fork_checkpoint_id": fork_id}
