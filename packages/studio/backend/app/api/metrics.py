from fastapi import APIRouter

from app.core.engine_service import get_engine

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    engine = get_engine()
    metrics = await engine.get_metrics()
    return metrics