from fastapi import APIRouter, HTTPException

from app.core.engine_service import get_engine

router = APIRouter()


@router.get("/events")
async def get_events(limit: int = 100):
    engine = get_engine()
    events = engine.get_recent_events(limit=limit)
    return {"events": events}


@router.get("/intents/{intent_id}")
async def get_intent(intent_id: str):
    engine = get_engine()
    timeline = await engine.get_intent_timeline(intent_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Intent not found")
    return {"intent_id": intent_id, "timeline": timeline}


@router.get("/intents")
async def list_intents(limit: int = 100):
    engine = get_engine()
    timeline = await engine.get_intent_timeline("*")
    return {"intents": timeline[-limit:]}