from typing import Optional
from fastapi import APIRouter, HTTPException

from app.core.engine_service import get_engine

router = APIRouter()


@router.get("/blackboard/keys")
async def list_keys():
    engine = get_engine()
    keys = await engine.list_keys()
    return {"keys": keys}


@router.get("/blackboard/keys/{key}")
async def get_key(key: str):
    engine = get_engine()
    try:
        value = await engine.get_key(key)
        return {"key": key, "value": value}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blackboard/keys/{key}")
async def set_key(key: str, body: dict):
    engine = get_engine()
    value = body.get("value")
    ttl = body.get("ttl")
    try:
        await engine.set_key(key, value, ttl=ttl)
        return {"key": key, "set": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/blackboard/keys/{key}")
async def delete_key(key: str):
    engine = get_engine()
    try:
        await engine.delete_key(key)
        return {"key": key, "deleted": True}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def get_audit_log(
    agent: str = "",
    key: str = "",
    limit: int = 50,
):
    engine = get_engine()
    entries = await engine.get_audit_log(agent=agent, key=key, limit=limit)
    return {"entries": entries}