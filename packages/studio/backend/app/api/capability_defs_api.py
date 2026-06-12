"""Capability definition CRUD for Studio capability market."""
from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.studio_persistence import load_json, save_json

router = APIRouter(prefix="/capability-defs", tags=["capability-defs"])

_STORE_FILE = "capability_defs.json"
_defs: dict[str, dict[str, Any]] = {}


class CapabilityDefRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    source: str = "external_service"
    endpoint: str = ""
    method: str = "POST"
    headers: dict = {}
    input_schema: dict = {}
    output_schema: dict = {}
    tags: list[str] = []
    config: dict = {}
    code: str = ""


def _serialize(item: dict) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "description": item.get("description", ""),
        "source": item.get("source", "external_service"),
        "endpoint": item.get("endpoint", ""),
        "method": item.get("method", "POST"),
        "headers": item.get("headers", {}),
        "input_schema": item.get("input_schema", {}),
        "output_schema": item.get("output_schema", {}),
        "tags": item.get("tags", []),
        "config": item.get("config", {}),
        "code": item.get("code", ""),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def load_capability_defs() -> None:
    global _defs
    raw = load_json(_STORE_FILE, {"definitions": []})
    _defs = {d["id"]: d for d in raw.get("definitions", []) if d.get("id")}


def persist_capability_defs() -> None:
    save_json(_STORE_FILE, {"definitions": list(_defs.values())})


@router.get("")
async def list_capability_defs():
    return {"capabilities": [_serialize(d) for d in _defs.values()]}


@router.post("")
async def create_capability_def(body: CapabilityDefRequest):
    cid = body.id or f"cap_{uuid.uuid4().hex[:8]}"
    now = time.time()
    record = {
        "id": cid,
        **body.model_dump(exclude={"id"}),
        "created_at": now,
        "updated_at": now,
    }
    _defs[cid] = record
    persist_capability_defs()
    return _serialize(record)


@router.put("/{cap_id}")
async def update_capability_def(cap_id: str, body: CapabilityDefRequest):
    if cap_id not in _defs:
        raise HTTPException(status_code=404, detail="Capability not found")
    record = _defs[cap_id]
    updates = body.model_dump(exclude={"id"}, exclude_unset=True)
    record.update(updates)
    record["updated_at"] = time.time()
    persist_capability_defs()
    return _serialize(record)


@router.delete("/{cap_id}")
async def delete_capability_def(cap_id: str):
    if cap_id not in _defs:
        raise HTTPException(status_code=404, detail="Capability not found")
    del _defs[cap_id]
    persist_capability_defs()
    return {"deleted": True, "id": cap_id}
