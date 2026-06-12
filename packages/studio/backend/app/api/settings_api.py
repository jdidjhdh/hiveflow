"""HiveFlow Studio - 运行时设置 API"""
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.core.engine_service import get_engine

router = APIRouter(prefix="/settings", tags=["settings"])


class SchedulerSettingsRequest(BaseModel):
    strategy: str = Field(..., pattern="^(least_loaded|auction)$")
    auction_timeout: float = Field(5.0, ge=1, le=60)


@router.get("/scheduler")
async def get_scheduler_settings():
    engine = get_engine()
    if not engine._running or engine.engine is None:
        raise HTTPException(status_code=503, detail="Engine not running")
    return engine.get_scheduler_settings()


@router.put("/scheduler")
async def update_scheduler_settings(req: SchedulerSettingsRequest):
    engine = get_engine()
    if not engine._running or engine.engine is None:
        raise HTTPException(status_code=503, detail="Engine not running")
    await engine.set_scheduler_settings(req.strategy, req.auction_timeout)
    return engine.get_scheduler_settings()
