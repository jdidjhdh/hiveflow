from typing import List, Optional
from fastapi import APIRouter, HTTPException

from app.core.engine_service import get_engine

router = APIRouter()


@router.get("/agents")
async def list_agents():
    engine = get_engine()
    agents = await engine.list_agents()
    return {"agents": agents}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    engine = get_engine()
    agent = await engine.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/agents")
async def register_agent(body: dict):
    engine = get_engine()
    agent_id = body.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    skills = body.get("skills", [])
    read_keys = body.get("read_keys", [])
    write_keys = body.get("write_keys", [])
    max_queue_size = body.get("max_queue_size")

    # Register a default echo handler if none provided
    async def default_handler(ecm, view):
        return {"result": "ok", "agent_id": agent_id}

    try:
        worker = await engine.create_agent(
            agent_id=agent_id,
            skills=skills,
            read_keys=read_keys,
            write_keys=write_keys,
            task_handler=default_handler,
            max_queue_size=max_queue_size,
        )
        return {"registered": True, "agent_id": agent_id, "state": worker.capability.state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    engine = get_engine()
    try:
        await engine.stop_agent(agent_id)
        return {"unregistered": True}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/agents/{agent_id}/drain")
async def drain_agent(agent_id: str):
    engine = get_engine()
    try:
        await engine.drain_agent(agent_id)
        return {"drained": True}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    engine = get_engine()
    try:
        await engine.stop_agent(agent_id)
        return {"stopped": True}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))