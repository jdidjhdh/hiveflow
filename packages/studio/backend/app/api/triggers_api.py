"""HiveFlow Studio - 触发器管理 API（内存存储，供 Studio 配置）"""
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/triggers", tags=["triggers"])

_triggers: dict[str, dict[str, Any]] = {}


class TriggerCreateRequest(BaseModel):
    name: str
    type: str  # webhook | schedule | event
    config: dict = {}
    enabled: bool = True
    workflow_id: Optional[str] = None


class TriggerUpdateRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None
    workflow_id: Optional[str] = None


def _serialize(trigger: dict) -> dict:
    return {
        "id": trigger["id"],
        "name": trigger["name"],
        "type": trigger["type"],
        "config": trigger.get("config", {}),
        "enabled": trigger.get("enabled", True),
        "workflow_id": trigger.get("workflow_id"),
        "created_at": trigger.get("created_at"),
    }


@router.get("")
async def list_triggers():
    return {"triggers": [_serialize(t) for t in _triggers.values()]}


@router.post("")
async def create_trigger(req: TriggerCreateRequest):
    trigger_id = f"trigger_{uuid.uuid4().hex[:8]}"
    _triggers[trigger_id] = {
        "id": trigger_id,
        "name": req.name,
        "type": req.type,
        "config": req.config,
        "enabled": req.enabled,
        "workflow_id": req.workflow_id,
        "created_at": time.time(),
    }
    return _serialize(_triggers[trigger_id])


@router.get("/{trigger_id}")
async def get_trigger(trigger_id: str):
    trigger = _triggers.get(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return _serialize(trigger)


@router.put("/{trigger_id}")
async def update_trigger(trigger_id: str, req: TriggerUpdateRequest):
    trigger = _triggers.get(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    if req.name is not None:
        trigger["name"] = req.name
    if req.type is not None:
        trigger["type"] = req.type
    if req.config is not None:
        trigger["config"] = req.config
    if req.enabled is not None:
        trigger["enabled"] = req.enabled
    if req.workflow_id is not None:
        trigger["workflow_id"] = req.workflow_id
    return _serialize(trigger)


@router.delete("/{trigger_id}")
async def delete_trigger(trigger_id: str):
    if trigger_id not in _triggers:
        raise HTTPException(status_code=404, detail="Trigger not found")
    del _triggers[trigger_id]
    return {"id": trigger_id, "status": "deleted"}


@router.post("/{trigger_id}/toggle")
async def toggle_trigger(trigger_id: str):
    trigger = _triggers.get(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    trigger["enabled"] = not trigger.get("enabled", True)
    return _serialize(trigger)
