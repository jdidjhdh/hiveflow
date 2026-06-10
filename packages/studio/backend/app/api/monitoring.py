"""HiveFlow Studio - 监控仪表板 API

提供 Prometheus 指标端点和 Studio 内部指标查询
"""
import time
import logging
from fastapi import APIRouter
from typing import Dict, Any

from app.core.engine_service import get_engine
from app.db.config import get_storage

logger = logging.getLogger(__name__)

# 启动时间
_startup_time: float = 0.0

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def set_startup_time(ts: float) -> None:
    """记录服务启动时间"""
    global _startup_time
    _startup_time = ts


@router.get("/metrics")
async def get_metrics() -> str:
    """Prometheus 格式的指标端点"""
    engine = get_engine()
    if hasattr(engine, '_metrics_exporter') and engine._metrics_exporter:
        return engine._metrics_exporter.generate_metrics()
    return "# No metrics exporter configured\n"


@router.get("/metrics/json")
async def get_metrics_json() -> Dict[str, Any]:
    """JSON 格式的内部指标"""
    engine = get_engine()
    return await engine.get_metrics_json()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查端点"""
    engine = get_engine()
    storage = get_storage()
    
    # 检查存储状态
    storage_status = "ok" if storage else "not_initialized"
    
    uptime = time.time() - _startup_time if _startup_time > 0 else 0
    
    return {
        "status": "healthy",
        "engine_mode": "real" if engine._ws_connected else "mock",
        "ws_connected": engine._ws_connected,
        "storage": storage_status,
        "uptime_seconds": round(uptime, 1),
        "version": "0.1.0",
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """详细健康检查（含各组件状态）"""
    engine = get_engine()
    storage = get_storage()
    
    checks = {
        "engine": {
            "status": "ok" if engine else "not_initialized",
            "ws_connected": engine._ws_connected if engine else False,
            "mode": "real" if engine and engine._ws_connected else "mock",
        },
        "storage": {
            "status": "ok" if storage else "not_initialized",
            "type": type(storage).__name__ if storage else None,
        },
    }
    
    overall = "healthy" if all(c["status"] == "ok" for c in checks.values()) else "degraded"
    
    return {
        "status": overall,
        "checks": checks,
        "uptime_seconds": round(time.time() - _startup_time, 1) if _startup_time > 0 else 0,
        "version": "0.1.0",
    }


@router.get("/traces")
async def get_traces(limit: int = 100) -> list:
    """获取最近的追踪数据"""
    engine = get_engine()
    if hasattr(engine, 'tracer') and engine.tracer:
        return engine.tracer.get_spans()[-limit:]
    return []


@router.get("/traces/{trace_id}")
async def get_trace_detail(trace_id: str) -> list:
    """获取指定 trace 的详细信息"""
    engine = get_engine()
    if hasattr(engine, 'tracer') and engine.tracer:
        return engine.tracer.get_trace_tree(trace_id)
    return []
