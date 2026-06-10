"""HiveFlow Studio - 数据分析 API

提供数据分析的 REST API，支持：
- 工作流执行统计
- Agent 性能指标
- 错误率分析
- 趋势数据
"""
import logging
import time
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter

from app.core.engine_service import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ======================== Routes ========================

@router.get("/summary")
async def get_analytics_summary(days: int = 7):
    """获取数据分析摘要"""
    engine = get_engine()
    
    # Get workflow stats
    workflow_stats = engine.get_workflow_stats()
    
    # Get agent stats
    agent_stats = engine.get_agent_stats()
    
    # Get event counts
    recent_events = engine.get_recent_events(limit=1000)
    
    return {
        "period_days": days,
        "workflows": {
            "total_executions": workflow_stats.get("total_executions", 0),
            "success_rate": workflow_stats.get("success_rate", 0),
            "avg_duration": workflow_stats.get("avg_duration", 0),
        },
        "agents": {
            "total": agent_stats.get("total", 0),
            "active": agent_stats.get("active", 0),
            "tasks_completed": agent_stats.get("tasks_completed", 0),
        },
        "events": {
            "total": len(recent_events),
            "errors": sum(1 for e in recent_events if e.get("type") == "error"),
            "warnings": sum(1 for e in recent_events if e.get("type") == "warning"),
        },
    }


@router.get("/workflows/trend")
async def get_workflow_trend(days: int = 7):
    """获取工作流执行趋势"""
    engine = get_engine()
    trend = engine.get_workflow_trend(days=days)
    return {"trend": trend, "period_days": days}


@router.get("/agents/performance")
async def get_agent_performance():
    """获取 Agent 性能数据"""
    engine = get_engine()
    agents = engine.get_agent_performance()
    return {"agents": agents}


@router.get("/errors")
async def get_error_analysis(limit: int = 50):
    """获取错误分析"""
    engine = get_engine()
    errors = engine.get_recent_errors(limit=limit)
    
    # Group by error type
    error_types = {}
    for err in errors:
        error_type = err.get("type", "unknown")
        if error_type not in error_types:
            error_types[error_type] = 0
        error_types[error_type] += 1
    
    return {
        "total_errors": len(errors),
        "error_types": error_types,
        "recent": errors[:10],
    }


@router.get("/blackboard")
async def get_blackboard_analytics():
    """获取黑板使用分析"""
    engine = get_engine()
    stats = engine.get_blackboard_stats()
    return {
        "total_keys": stats.get("total_keys", 0),
        "total_writes": stats.get("total_writes", 0),
        "total_reads": stats.get("total_reads", 0),
        "hit_rate": stats.get("hit_rate", 0),
    }


@router.get("/rag")
async def get_rag_analytics():
    """获取 RAG/知识库使用分析"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    kbs = await kb_manager.list_kbs()
    
    total_docs = sum(kb.doc_count for kb in kbs)
    total_queries = sum(kb.query_count if hasattr(kb, 'query_count') else 0 for kb in kbs)
    
    return {
        "knowledge_bases": len(kbs),
        "total_documents": total_docs,
        "total_queries": total_queries,
    }


@router.get("/plugins")
async def get_plugin_analytics():
    """获取插件使用分析"""
    engine = get_engine()
    plugin_manager = engine.get_plugin_manager()
    plugins = await plugin_manager.list_plugins()
    
    total_calls = sum(p.call_count if hasattr(p, 'call_count') else 0 for p in plugins)
    
    return {
        "installed_plugins": len(plugins),
        "total_calls": total_calls,
    }
