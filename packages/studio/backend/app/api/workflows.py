"""HiveFlow Studio - 工作流 API"""
import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.core.engine_service import get_engine
from app.core.workflow_graph_builder import build_taskgraph_from_workflow, normalize_studio_node
from app.db.config import get_storage
from app.db.base import WorkflowRecord

router = APIRouter()


@router.post("/workflows")
async def save_workflow(body: dict):
    """保存工作流定义到数据库"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    wf_id = body.get("id") or f"wf_{uuid.uuid4().hex[:8]}"

    workflow = WorkflowRecord(
        id=wf_id,
        name=body.get("name", ""),
        description=body.get("description", ""),
        graph=body.get("graph", {}),
        nodes=body.get("nodes", []),
        edges=body.get("edges", []),
        metadata=body.get("metadata", {}),
    )

    wf_id = await storage.create_workflow(workflow)
    return {"id": wf_id, "saved": True}


@router.get("/workflows")
async def list_workflows(limit: int = 100, offset: int = 0):
    """列出所有工作流"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    workflows = await storage.list_workflows(limit=limit, offset=offset)
    return {
        "workflows": [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "version": wf.version,
                "updated_at": wf.updated_at,
            }
            for wf in workflows
        ]
    }


@router.get("/workflows/{wf_id}")
async def get_workflow(wf_id: str):
    """获取工作流详情"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    workflow = await storage.get_workflow(wf_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "graph": workflow.graph,
        "nodes": workflow.nodes,
        "edges": workflow.edges,
        "version": workflow.version,
        "metadata": workflow.metadata,
        "updated_at": workflow.updated_at,
    }


@router.put("/workflows/{wf_id}")
async def update_workflow(wf_id: str, body: dict):
    """更新工作流（自动创建新版本）"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    record = await storage.get_workflow(wf_id)
    if not record:
        raise HTTPException(status_code=404, detail="Workflow not found")

    success = await storage.update_workflow(
        wf_id,
        name=body.get("name", record.name),
        description=body.get("description", record.description),
        graph=body.get("graph", record.graph),
        nodes=body.get("nodes", record.nodes),
        edges=body.get("edges", record.edges),
        metadata=body.get("metadata", record.metadata),
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update workflow")

    return {"id": wf_id, "updated": True, "version": record.version + 1}


@router.delete("/workflows/{wf_id}")
async def delete_workflow(wf_id: str):
    """删除工作流及其所有版本"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    deleted = await storage.delete_workflow(wf_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return {"deleted": True}


@router.post("/workflows/{wf_id}/execute")
async def execute_workflow(wf_id: str, body: Optional[dict] = None):
    """执行已保存的工作流"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    workflow = await storage.get_workflow(wf_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    engine = get_engine()

    graph = build_taskgraph_from_workflow(
        workflow.nodes,
        workflow.edges,
        _make_task_fn_from_node,
    )

    mode = "dag"
    global_timeout = (body or {}).get("global_timeout")

    try:
        result = await engine.execute_workflow(
            wf_id=wf_id,
            graph=graph,
            mode=mode,
            global_timeout=global_timeout,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflows/{wf_id}/export")
async def export_workflow(wf_id: str):
    """导出工作流为JSON（包含版本和元数据）"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    workflow = await storage.get_workflow(wf_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "version": workflow.version,
        "graph": workflow.graph,
        "nodes": workflow.nodes,
        "edges": workflow.edges,
        "metadata": workflow.metadata,
        "exported_at": datetime.now().isoformat(),
        "format": "hflow/v1",
    }


@router.post("/workflows/import")
async def import_workflow(body: dict):
    """从JSON导入工作流"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    wf_id = body.get("id") or f"wf_{uuid.uuid4().hex[:8]}"
    # Ensure unique ID
    existing = await storage.get_workflow(wf_id)
    if existing:
        wf_id = f"wf_{uuid.uuid4().hex[:8]}"

    workflow = WorkflowRecord(
        id=wf_id,
        name=body.get("name", "Imported Workflow"),
        description=body.get("description", ""),
        graph=body.get("graph", {}),
        nodes=body.get("nodes", []),
        edges=body.get("edges", []),
        metadata={**body.get("metadata", {}), "imported": True},
    )

    imported_id = await storage.create_workflow(workflow)
    return {"id": imported_id, "imported": True, "name": workflow.name}


@router.post("/workflows/batch-export")
async def batch_export_workflows(body: Optional[dict] = None):
    """批量导出所有工作流"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    workflows = await storage.list_workflows(limit=1000, offset=0)
    result = []
    for wf in workflows:
        result.append({
            "id": wf.id,
            "name": wf.name,
            "description": wf.description,
            "version": wf.version,
            "graph": wf.graph,
            "nodes": wf.nodes,
            "edges": wf.edges,
            "metadata": wf.metadata,
        })

    return {
        "workflows": result,
        "count": len(result),
        "exported_at": datetime.now().isoformat(),
        "format": "hflow/v1",
    }


@router.get("/workflows/{wf_id}/status")
async def get_workflow_status(wf_id: str):
    """获取工作流执行状态"""
    engine = get_engine()
    return engine.get_workflow_status(wf_id)


@router.post("/workflows/{wf_id}/stop")
async def stop_workflow(wf_id: str):
    """停止工作流执行"""
    engine = get_engine()
    return await engine.stop_workflow(wf_id)


@router.post("/workflows/execute")
async def execute_workflow_direct(body: dict):
    """直接执行工作流图（来自前端的实时编排）"""
    graph_spec = body.get("graph", {})
    if not graph_spec:
        raise HTTPException(status_code=400, detail="Empty graph")

    engine = get_engine()
    wf_id = f"wf_{uuid.uuid4().hex[:8]}"

    graph = {}
    for node_id, node_data in graph_spec.items():
        graph[node_id] = {
            "task": _make_task_fn_from_spec(node_id, node_data),
            "depends_on": node_data.get("depends_on", []),
            "on_failure": node_data.get("on_failure", "abort"),
            "retry_policy": node_data.get("retry_policy", {}),
            "dynamic": node_data.get("dynamic", False),
            "variant": node_data.get("variant", "task"),
            "hitl_config": node_data.get("hitl_config", {}),
        }

    try:
        result = await engine.execute_workflow(
            wf_id=wf_id,
            graph=graph,
            mode="dag",
            global_timeout=body.get("global_timeout"),
            enable_guard=body.get("enable_guard", True),
            enable_checkpoint=body.get("enable_checkpoint", True),
        )
        outer_status = result.get("status", "completed")
        return {
            "wf_id": wf_id,
            "status": outer_status,
            "result": result,
            "results": result.get("results") if isinstance(result, dict) else result,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 版本管理 ==========

@router.get("/workflows/{wf_id}/versions")
async def get_workflow_versions(wf_id: str):
    """获取工作流历史版本列表"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    record = await storage.get_workflow(wf_id)
    if not record:
        raise HTTPException(status_code=404, detail="Workflow not found")

    versions = await storage.get_workflow_versions(wf_id)
    return {
        "workflow_id": wf_id,
        "current_version": record.version,
        "versions": [
            {
                "version": v.version,
                "name": v.name,
                "created_at": v.created_at,
                "metadata": v.metadata,
            }
            for v in versions
        ]
    }


@router.get("/workflows/{wf_id}/versions/{version}")
async def get_workflow_version(wf_id: str, version: int):
    """获取指定版本的完整工作流定义"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    versions = await storage.get_workflow_versions(wf_id)
    target = next((v for v in versions if v.version == version), None)

    if not target:
        raise HTTPException(status_code=404, detail="Version not found")

    return {
        "id": target.id,
        "workflow_id": wf_id,
        "version": target.version,
        "name": target.name,
        "description": target.description,
        "graph": target.graph,
        "nodes": target.nodes,
        "edges": target.edges,
        "metadata": target.metadata,
        "created_at": target.created_at,
    }


@router.post("/workflows/{wf_id}/rollback/{version}")
async def rollback_workflow(wf_id: str, version: int):
    """回滚到指定版本"""
    storage = get_storage()
    if not storage:
        raise HTTPException(status_code=500, detail="Storage not initialized")

    record = await storage.get_workflow(wf_id)
    if not record:
        raise HTTPException(status_code=404, detail="Workflow not found")

    success = await storage.rollback_workflow(wf_id, version)
    if not success:
        raise HTTPException(status_code=404, detail="Version not found")

    return {"id": wf_id, "rolled_back": True, "new_version": record.version + 1}


# ========== 辅助函数 ==========

def _make_task_fn_from_spec(node_id: str, node_data: dict):
    """Create an async task function from a TaskGraph node specification."""
    normalized = {
        "id": node_id,
        "task": node_data.get("task", node_id),
        "variant": node_data.get("variant", "task"),
        "code": node_data.get("code", ""),
        "config": node_data.get("config", {}),
    }
    return _make_task_fn_from_node(normalized)


def _make_task_fn_from_node(node: dict):
    """Create an async task function from a normalized Studio node."""
    node_id = node.get("id") or "unknown"
    task_name = node.get("task") or node_id
    variant = node.get("variant", "task")
    code = node.get("code") or ""
    config = node.get("config") or {}

    async def task_fn(deps, blackboard):
        if variant == "hitl":
            return {"node": node_id, "task": task_name, "awaiting": "hitl"}

        if variant == "code" and code.strip():
            local_vars: dict = {"deps": deps, "result": None}
            exec(code, {"__builtins__": {}}, local_vars)  # noqa: S102
            return local_vars.get("result", {"node": node_id, "executed": True})

        if config.get("value") is not None:
            return {"output": config.get("value"), "node": node_id, "task": task_name}

        await asyncio.sleep(0.05)
        return {"node": node_id, "task": task_name, "deps": list(deps.keys())}

    return task_fn


def _make_task_fn(node: dict):
    """Legacy entry: normalize ReactFlow node then build task."""
    return _make_task_fn_from_node(normalize_studio_node(node))
