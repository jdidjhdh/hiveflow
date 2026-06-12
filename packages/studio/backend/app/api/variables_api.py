"""HiveFlow Studio - 变量管理 API

提供全局变量的 REST API，支持：
- 变量 CRUD
- 变量类型（string/number/boolean/json/secret）
- 变量引用解析
"""
import logging
from typing import Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/variables", tags=["variables"])

# 内存存储变量（生产环境应使用数据库）
_variables: dict[str, dict[str, Any]] = {}


# ======================== Models ========================

class VariableCreateRequest(BaseModel):
    name: str
    value: Any
    var_type: str = "string"  # string, number, boolean, json, secret
    description: str = ""
    scope: str = "global"


class VariableUpdateRequest(BaseModel):
    value: Optional[Any] = None
    description: Optional[str] = None
    scope: Optional[str] = None


# ======================== Routes ========================

@router.get("")
async def list_variables():
    """列出所有变量"""
    return {
        "variables": [
            {
                "name": v["name"],
                "value": "****" if v["var_type"] == "secret" else v["value"],
                "var_type": v["var_type"],
                "description": v["description"],
                "scope": v.get("scope", "global"),
                "created_at": v.get("created_at"),
            }
            for v in _variables.values()
        ]
    }


@router.post("")
async def create_variable(req: VariableCreateRequest):
    """创建变量"""
    import time
    if req.name in _variables:
        raise HTTPException(status_code=409, detail=f"Variable '{req.name}' already exists")

    _variables[req.name] = {
        "name": req.name,
        "value": req.value,
        "var_type": req.var_type,
        "description": req.description,
        "scope": req.scope,
        "created_at": time.time(),
    }
    return {"name": req.name, "status": "created"}


@router.get("/resolve")
async def resolve_variables(expression: str):
    """解析变量引用表达式（须在 /{var_name} 之前注册）"""
    import re

    def replace_var(match):
        var_name = match.group(1)
        var = _variables.get(var_name)
        if var:
            return str(var["value"])
        return match.group(0)

    resolved = re.sub(r'\$\{([^}]+)\}', replace_var, expression)
    return {
        "expression": expression,
        "resolved": resolved,
        "variables_found": re.findall(r'\$\{([^}]+)\}', expression),
    }


@router.get("/{var_name}")
async def get_variable(var_name: str):
    """获取变量值"""
    var = _variables.get(var_name)
    if not var:
        raise HTTPException(status_code=404, detail=f"Variable '{var_name}' not found")
    value = "****" if var["var_type"] == "secret" else var["value"]
    return {
        "name": var["name"],
        "value": value,
        "var_type": var["var_type"],
        "description": var["description"],
        "scope": var.get("scope", "global"),
    }


@router.put("/{var_name}")
async def update_variable(var_name: str, req: VariableUpdateRequest):
    """更新变量"""
    var = _variables.get(var_name)
    if not var:
        raise HTTPException(status_code=404, detail=f"Variable '{var_name}' not found")

    if req.value is not None:
        var["value"] = req.value
    if req.description is not None:
        var["description"] = req.description
    if req.scope is not None:
        var["scope"] = req.scope

    return {"name": var_name, "status": "updated"}


@router.delete("/{var_name}")
async def delete_variable(var_name: str):
    """删除变量"""
    if var_name not in _variables:
        raise HTTPException(status_code=404, detail=f"Variable '{var_name}' not found")

    del _variables[var_name]
    return {"name": var_name, "status": "deleted"}
