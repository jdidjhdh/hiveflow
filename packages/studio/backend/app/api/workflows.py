"""HiveFlow Studio - 工作流 API"""
import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.core.engine_service import get_engine
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

    # Build TaskGraph from workflow definition
    graph = {}
    for node in workflow.nodes:
        node_id = node.get("id")
        if not node_id:
            continue
        node_data = {
            "task": _make_task_fn(node),
            "depends_on": node.get("depends_on", []),
            "on_failure": node.get("on_failure", "abort"),
            "retry_policy": node.get("retry_policy", {}),
            "dynamic": node.get("dynamic", False),
        }
        graph[node_id] = node_data

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
    from app.main import _broadcast_workflow_status

    graph_spec = body.get("graph", {})
    if not graph_spec:
        raise HTTPException(status_code=400, detail="Empty graph")

    engine = get_engine()
    wf_id = f"wf_{uuid.uuid4().hex[:8]}"

    # Build TaskGraph
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
        return {"wf_id": wf_id, "status": "completed", "result": result}
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
    """Create an async task function from a node specification."""
    task_name = node_data.get("task", node_id)
    variant = node_data.get("variant", "task")

    async def task_fn(deps, blackboard):
        if variant == "hitl":
            # Execution is handled by EngineService HITL wrapper
            return {"node": node_id, "task": task_name, "awaiting": "hitl"}

        if variant == "code":
            code = node_data.get("code", "")
            if code.strip():
                local_vars: dict = {"deps": deps, "result": None}
                exec(code, {"__builtins__": {}}, local_vars)  # noqa: S102
                return local_vars.get("result", {"node": node_id, "executed": True})
            return {"node": node_id, "task": task_name, "variant": "code"}

        await asyncio.sleep(0.1)
        return {"node": node_id, "task": task_name, "deps": list(deps.keys())}

    return task_fn


def _make_task_fn(node: dict):
    """Create an async task function from a node definition."""
    node_type = node.get("type", "echo")
    config = node.get("config", {})

    async def task_fn(deps, blackboard):
        # Simple task implementation based on node type
        if node_type == "echo":
            return {"output": config.get("value", "ok"), "node": node.get("id")}
        elif node_type == "transform":
            # Try to get deps and transform
            combined = {}
            for dep_name, dep_val in deps.items():
                if dep_val is not None and not isinstance(dep_val, object):
                    combined[dep_name] = dep_val
            return {"input": combined, "transform": config.get("operation", "passthrough")}
        elif node_type == "sleep":
            duration = config.get("duration", 0.1)
            await asyncio.sleep(duration)
            return {"node": node.get("id"), "duration": duration}
        else:
            return {"node": node.get("id"), "type": node_type}

    return task_fn
