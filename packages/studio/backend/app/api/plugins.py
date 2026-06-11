"""HiveFlow Studio - 插件市场 API

提供插件市场的 REST API，支持：
- 浏览所有可用插件
- 按分类筛选
- 搜索插件
- 安装/卸载插件
- 查看已安装插件
"""
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.core.engine_service import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["plugins"])


# ======================== Models ========================

class PluginInstallRequest(BaseModel):
    plugin_id: str
    config: dict = {}


class PluginUninstallRequest(BaseModel):
    plugin_id: str


# ======================== Routes ========================

@router.get("/marketplace")
async def list_marketplace_plugins(category: Optional[str] = None, q: Optional[str] = None):
    """列出插件市场中所有可用插件"""
    from hiveflow import PluginMarketplace, PluginCategory

    marketplace = PluginMarketplace()

    if q:
        plugins = marketplace.search_plugins(q)
    elif category:
        try:
            cat = PluginCategory(category)
            plugins = marketplace.list_plugins(category=cat)
        except ValueError:
            plugins = marketplace.list_plugins()
    else:
        plugins = marketplace.list_plugins()

    return {
        "plugins": [p.to_dict() for p in plugins],
        "stats": marketplace.get_stats(),
    }


@router.get("/marketplace/categories")
async def list_categories():
    """列出所有插件分类"""
    from hiveflow import PluginMarketplace

    marketplace = PluginMarketplace()
    categories = marketplace.get_categories()
    return {"categories": {c.value: n for c, n in categories.items()}}


@router.get("/marketplace/{plugin_id}")
async def get_marketplace_plugin(plugin_id: str):
    """获取插件详情"""
    from hiveflow import PluginMarketplace

    marketplace = PluginMarketplace()
    plugin = marketplace.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return plugin.to_dict()


@router.get("/installed")
async def list_installed_plugins():
    """列出已安装的插件"""
    engine = get_engine()
    plugin_manager = engine.get_plugin_manager()
    plugins = await plugin_manager.list_plugins()
    return {
        "plugins": [
            {
                "plugin_id": p.plugin_id,
                "name": p.name,
                "description": p.description,
                "transport": p.transport,
                "command": p.command,
                "status": p.status if hasattr(p, 'status') else "unknown",
            }
            for p in plugins
        ]
    }


@router.post("/install")
async def install_plugin(req: PluginInstallRequest):
    """从插件市场安装插件"""
    from hiveflow import PluginMarketplace

    engine = get_engine()
    plugin_manager = engine.get_plugin_manager()
    marketplace = PluginMarketplace()

    success = await marketplace.install_plugin(req.plugin_id, plugin_manager, **req.config)
    if not success:
        raise HTTPException(status_code=404, detail=f"Plugin '{req.plugin_id}' not found in marketplace")

    registered_skills: list[str] = []
    try:
        registered_skills = await engine.auto_register_mcp_skills(req.plugin_id)
    except Exception as exc:
        logger.warning("Auto-register MCP skills failed for %s: %s", req.plugin_id, exc)

    return {
        "plugin_id": req.plugin_id,
        "status": "installed",
        "registered_skills": registered_skills,
    }


@router.post("/uninstall")
async def uninstall_plugin(req: PluginUninstallRequest):
    """卸载已安装的插件"""
    engine = get_engine()
    plugin_manager = engine.get_plugin_manager()

    # Note: MCPPluginManager may not have uninstall method yet
    # For now, we just remove from registry
    try:
        await plugin_manager.unregister_plugin(req.plugin_id)
        return {"plugin_id": req.plugin_id, "status": "uninstalled"}
    except AttributeError:
        raise HTTPException(status_code=501, detail="Uninstall not yet supported")


@router.get("/stats")
async def get_plugin_stats():
    """获取插件统计信息"""
    from hiveflow import PluginMarketplace

    marketplace = PluginMarketplace()
    engine = get_engine()
    plugin_manager = engine.get_plugin_manager()

    plugins = await plugin_manager.list_plugins()

    return {
        "marketplace": marketplace.get_stats(),
        "installed_count": len(plugins),
    }
