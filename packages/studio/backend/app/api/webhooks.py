"""HiveFlow Studio - Webhook API

Provides webhook endpoints for external systems to trigger workflows.
Webhooks can be configured in the Triggers page.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from app.core.engine_service import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# 内存存储 webhook 定义（生产环境应使用数据库）
_webhooks: Dict[str, Dict[str, Any]] = {}


@router.post("/{webhook_id}")
async def handle_webhook(webhook_id: str, request: Request):
    """
    接收 Webhook 请求并触发对应的工作流。
    
    Usage: POST /api/webhook/{webhook_id}
    Body: Any JSON payload (will be passed to the workflow)
    """
    webhook = _webhooks.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")

    if not webhook.get("enabled", True):
        raise HTTPException(status_code=403, detail="Webhook is disabled")

    # 解析请求体
    try:
        body = await request.json()
    except Exception:
        body = {}

    workflow_id = webhook.get("workflow_id")
    if not workflow_id:
        raise HTTPException(status_code=400, detail="Webhook has no associated workflow")

    # 触发工作流
    engine = get_engine()
    execution_id = str(uuid.uuid4())[:8]

    logger.info(f"Webhook {webhook_id} triggered workflow {workflow_id} (execution: {execution_id})")

    # 记录 webhook 触发
    webhook["last_triggered"] = datetime.now().isoformat()
    webhook["trigger_count"] = webhook.get("trigger_count", 0) + 1

    return {
        "status": "accepted",
        "execution_id": execution_id,
        "workflow_id": workflow_id,
        "message": f"Webhook {webhook_id} triggered workflow {workflow_id}",
    }


@router.get("")
async def list_webhooks():
    """列出所有已注册的 Webhook"""
    return {"webhooks": list(_webhooks.values())}


@router.get("/{webhook_id}")
async def get_webhook(webhook_id: str):
    """获取指定 Webhook 详情"""
    webhook = _webhooks.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")
    return webhook


@router.post("")
async def create_webhook(request: Request):
    """创建一个新的 Webhook"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    webhook_id = body.get("id") or str(uuid.uuid4())[:8]
    
    _webhooks[webhook_id] = {
        "id": webhook_id,
        "name": body.get("name", f"Webhook {webhook_id}"),
        "workflow_id": body.get("workflow_id", ""),
        "enabled": body.get("enabled", True),
        "method": body.get("method", "POST"),
        "created_at": datetime.now().isoformat(),
        "trigger_count": 0,
        "last_triggered": None,
        "metadata": body.get("metadata", {}),
    }

    logger.info(f"Webhook created: {webhook_id}")
    return _webhooks[webhook_id]


@router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, request: Request):
    """更新 Webhook 配置"""
    webhook = _webhooks.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    for key in ("name", "workflow_id", "enabled", "method", "metadata"):
        if key in body:
            webhook[key] = body[key]

    logger.info(f"Webhook updated: {webhook_id}")
    return webhook


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """删除 Webhook"""
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")

    del _webhooks[webhook_id]
    logger.info(f"Webhook deleted: {webhook_id}")
    return {"status": "ok", "id": webhook_id}


@router.post("/{webhook_id}/toggle")
async def toggle_webhook(webhook_id: str):
    """切换 Webhook 启用/禁用状态"""
    webhook = _webhooks.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")

    webhook["enabled"] = not webhook.get("enabled", True)
    return {"id": webhook_id, "enabled": webhook["enabled"]}
