"""HiveMind Agent mode API for Studio."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.engine_service import get_engine

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None


class ExecutePlanRequest(BaseModel):
    plan: dict
    query: str = Field(default="Execute workflow plan")
    conversation_id: Optional[str] = None


class ExportLangGraphRequest(BaseModel):
    plan: dict
    workflow_id: str = Field(default="studio_export")
    include_python: bool = False


class RuntimeModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(core|agent)$")


@router.get("/runtime")
async def get_runtime():
    engine = get_engine()
    return engine.get_runtime_info()


@router.post("/runtime")
async def set_runtime(body: RuntimeModeRequest):
    engine = get_engine()
    try:
        return await engine.set_runtime_mode(body.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/query")
async def agent_query(body: AgentQueryRequest):
    engine = get_engine()
    try:
        result = await engine.run_agent_query(body.query, body.conversation_id)
        engine.record_intent(
            result.get("intent_id", "unknown"),
            "agent_query",
            "studio",
            result.get("status", "completed"),
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan-only")
async def agent_plan_only(body: AgentQueryRequest):
    engine = get_engine()
    try:
        result = await engine.run_agent_plan_only(body.query, body.conversation_id)
        engine.record_intent(
            result.get("intent_id", "unknown"),
            "agent_plan",
            "studio",
            "planned",
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-langgraph")
async def export_langgraph(body: ExportLangGraphRequest):
    """Convert a TaskGraph plan to LangGraph-oriented JSON (PoC adapter)."""
    from app.utils.plan_export import normalize_studio_plan
    from hiveflow.adapters.langgraph import (
        dumps_langgraph_spec,
        render_langgraph_python,
        taskgraph_to_langgraph,
    )

    plan = normalize_studio_plan(body.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="plan must contain at least one node")

    try:
        spec = taskgraph_to_langgraph(plan, workflow_id=body.workflow_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    payload = {
        "spec": spec,
        "spec_json": dumps_langgraph_spec(spec),
        "node_count": len(plan),
    }
    if body.include_python:
        payload["python"] = render_langgraph_python(spec)
    return payload


@router.post("/execute-plan")
async def agent_execute_plan(body: ExecutePlanRequest):
    engine = get_engine()
    import time

    t0 = time.monotonic()
    try:
        result = await engine.run_agent_execute_plan(
            body.plan, body.query, body.conversation_id,
        )
        elapsed_ms = (time.monotonic() - t0) * 1000
        intent_id = result.get("intent_id", "unknown")
        per_node = elapsed_ms / max(len(body.plan), 1)
        for node_name in body.plan.keys():
            engine.record_node_execution(node_name, per_node, intent_id)
        engine.record_intent(intent_id, "agent_execute_plan", "studio", result.get("status", "completed"))
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/{plugin_id}/register-skills")
async def register_mcp_skills(plugin_id: str):
    engine = get_engine()
    try:
        skills = await engine.register_mcp_as_skills(plugin_id)
        return {"plugin_id": plugin_id, "skills": skills}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
