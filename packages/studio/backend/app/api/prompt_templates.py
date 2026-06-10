"""HiveFlow Studio - Prompt 模板库 API

提供 Prompt 模板的 REST API，支持：
- 模板 CRUD
- 版本管理（每次更新自动创建新版本）
- 版本回滚/对比
- 模板分类/标签
- 模板测试
"""
import logging
import time
import uuid
import difflib
import re
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompt-templates", tags=["prompt-templates"])

_templates: dict[str, dict] = {}
_template_versions: dict[str, list] = {}


class TemplateCreateRequest(BaseModel):
    name: str
    content: str
    category: str = "general"
    description: str = ""
    tags: list[str] = []
    variables: list[str] = []
    model_hints: list[str] = []


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    variables: Optional[list[str]] = None
    model_hints: Optional[list[str]] = None


class TemplateTestRequest(BaseModel):
    version: Optional[int] = None
    variables: dict = {}


def _compute_next_version(template_id: str) -> int:
    versions = _template_versions.get(template_id, [])
    if not versions:
        return 1
    return max(v["version"] for v in versions) + 1


def _save_version(template_id: str, content: str, change_summary: str = "") -> int:
    version = _compute_next_version(template_id)
    _template_versions.setdefault(template_id, []).append({
        "version": version,
        "content": content,
        "created_at": time.time(),
        "created_by": "system",
        "change_summary": change_summary,
    })
    return version


# ===== Collection-level routes (MUST come before /{template_id}) =====

@router.get("")
async def list_templates(
    category: Optional[str] = None,
    q: Optional[str] = None,
    tag: Optional[str] = None,
):
    templates = list(_templates.values())
    if category:
        templates = [t for t in templates if t["category"] == category]
    if q:
        ql = q.lower()
        templates = [
            t for t in templates
            if ql in t["name"].lower() or ql in t.get("description", "").lower()
            or ql in " ".join(t.get("tags", [])).lower()
        ]
    if tag:
        templates = [t for t in templates if tag in t.get("tags", [])]
    return {
        "templates": [
            {
                "id": t["id"], "name": t["name"], "category": t["category"],
                "description": t.get("description", ""), "tags": t.get("tags", []),
                "variables": t.get("variables", []), "model_hints": t.get("model_hints", []),
                "current_version": t["current_version"],
                "total_versions": len(_template_versions.get(t["id"], [])),
                "created_at": t["created_at"], "updated_at": t["updated_at"],
            }
            for t in templates
        ],
        "categories": list(set(t["category"] for t in templates)),
    }


@router.post("")
async def create_template(req: TemplateCreateRequest):
    template_id = str(uuid.uuid4())[:8]
    now = time.time()
    version = _save_version(template_id, req.content)
    _templates[template_id] = {
        "id": template_id, "name": req.name, "content": req.content,
        "category": req.category, "description": req.description,
        "tags": req.tags, "variables": req.variables, "model_hints": req.model_hints,
        "current_version": version, "created_at": now, "updated_at": now,
    }
    return {"id": template_id, "name": req.name, "current_version": version, "status": "created"}


@router.get("/categories")
async def list_categories():
    cats = {}
    for t in _templates.values():
        cats[t["category"]] = cats.get(t["category"], 0) + 1
    return {"categories": cats}


@router.post("/seed")
async def seed_templates():
    defaults = [
        {"name": "通用助手", "content": "You are a helpful assistant. {{system_instructions}}\n\nUser: {{user_input}}\nAssistant:", "category": "chat", "description": "通用对话助手模板", "tags": ["assistant", "chat"], "variables": ["system_instructions", "user_input"]},
        {"name": "RAG 问答", "content": "Based on the following context, answer the user's question.\n\nContext:\n{{context}}\n\nQuestion: {{question}}\n\nAnswer:", "category": "rag", "description": "基于上下文的 RAG 问答模板", "tags": ["rag", "qa"], "variables": ["context", "question"]},
        {"name": "代码生成", "content": "You are an expert programmer. Write code based on the requirements.\n\nLanguage: {{language}}\nRequirements: {{requirements}}\nConstraints: {{constraints}}\n\n", "category": "tool", "description": "代码生成模板", "tags": ["code", "generation"], "variables": ["language", "requirements", "constraints"]},
        {"name": "Agent 系统提示", "content": "You are an AI agent with the following capabilities:\n{{capabilities}}\n\nYour role: {{role}}\nYour goal: {{goal}}\n\nRules:\n1. {{rule_1}}\n2. {{rule_2}}\n3. {{rule_3}}\n\nBegin.", "category": "agent", "description": "Agent 系统提示词模板", "tags": ["agent", "system"], "variables": ["capabilities", "role", "goal", "rule_1", "rule_2", "rule_3"]},
        {"name": "JSON 提取器", "content": "Extract the following information from the text as JSON:\n\nText: {{input_text}}\nFields to extract: {{fields}}\n\nJSON:", "category": "tool", "description": "从文本中提取 JSON 的模板", "tags": ["json", "extraction"], "variables": ["input_text", "fields"]},
        {"name": "文本摘要", "content": "Summarize the following text in {{max_words}} words or less:\n\n{{text}}\n\nSummary:", "category": "general", "description": "文本摘要模板", "tags": ["summarization"], "variables": ["text", "max_words"]},
        {"name": "意图识别", "content": "Identify the user's intent from the following text. Return as JSON with 'intent' and 'confidence' fields.\n\nText: {{user_input}}\n\nAvailable intents: {{available_intents}}", "category": "agent", "description": "用户意图识别模板", "tags": ["intent", "classification"], "variables": ["user_input", "available_intents"]},
    ]
    created = []
    for t in defaults:
        tid = str(uuid.uuid4())[:8]
        now = time.time()
        v = _save_version(tid, t["content"])
        _templates[tid] = {
            "id": tid, "name": t["name"], "content": t["content"],
            "category": t["category"], "description": t["description"],
            "tags": t["tags"], "variables": t["variables"], "model_hints": [],
            "current_version": v, "created_at": now, "updated_at": now,
        }
        created.append({"id": tid, "name": t["name"]})
    return {"seeded": len(created), "templates": created}


# ===== Parameterized routes =====

@router.get("/{template_id}")
async def get_template(template_id: str, version: Optional[int] = None):
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    if version:
        versions = _template_versions.get(template_id, [])
        ve = next((v for v in versions if v["version"] == version), None)
        if not ve:
            raise HTTPException(status_code=404, detail=f"Version {version} not found")
        content = ve["content"]
    else:
        content = template["content"]
    return {
        "id": template["id"], "name": template["name"], "content": content,
        "category": template["category"], "description": template.get("description", ""),
        "tags": template.get("tags", []), "variables": template.get("variables", []),
        "model_hints": template.get("model_hints", []),
        "current_version": template["current_version"],
        "requested_version": version or template["current_version"],
        "created_at": template["created_at"], "updated_at": template["updated_at"],
    }


@router.put("/{template_id}")
async def update_template(template_id: str, req: TemplateUpdateRequest):
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    old_content = template["content"]
    if req.content is not None and req.content != old_content:
        version = _save_version(template_id, req.content, "Content updated")
        template["current_version"] = version
        template["content"] = req.content
    elif req.content is not None:
        _save_version(template_id, old_content, "Metadata updated")
    else:
        _save_version(template_id, old_content, "Metadata updated")
    if req.name is not None: template["name"] = req.name
    if req.category is not None: template["category"] = req.category
    if req.description is not None: template["description"] = req.description
    if req.tags is not None: template["tags"] = req.tags
    if req.variables is not None: template["variables"] = req.variables
    if req.model_hints is not None: template["model_hints"] = req.model_hints
    template["updated_at"] = time.time()
    return {"id": template_id, "current_version": template["current_version"], "status": "updated"}


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    del _templates[template_id]
    _template_versions.pop(template_id, None)
    return {"id": template_id, "status": "deleted"}


@router.get("/{template_id}/versions")
async def list_versions(template_id: str):
    if template_id not in _templates:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    versions = _template_versions.get(template_id, [])
    return {
        "template_id": template_id,
        "versions": [
            {"version": v["version"], "created_at": v["created_at"],
             "created_by": v["created_by"], "change_summary": v["change_summary"],
             "content_length": len(v["content"])}
            for v in sorted(versions, key=lambda x: x["version"])
        ],
    }


@router.get("/{template_id}/versions/{version}")
async def get_version(template_id: str, version: int):
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    versions = _template_versions.get(template_id, [])
    ve = next((v for v in versions if v["version"] == version), None)
    if not ve:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    return {"template_id": template_id, "version": version, "content": ve["content"],
            "created_at": ve["created_at"], "change_summary": ve["change_summary"]}


@router.post("/{template_id}/rollback/{version}")
async def rollback_version(template_id: str, version: int):
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    versions = _template_versions.get(template_id, [])
    ve = next((v for v in versions if v["version"] == version), None)
    if not ve:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    new_version = _save_version(template_id, ve["content"], f"Rolled back to version {version}")
    template["content"] = ve["content"]
    template["current_version"] = new_version
    template["updated_at"] = time.time()
    return {"id": template_id, "current_version": new_version, "rolled_back_to": version, "status": "rolled_back"}


@router.post("/{template_id}/compare")
async def compare_versions(template_id: str, version_a: int, version_b: int):
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    versions = _template_versions.get(template_id, [])
    va = next((v for v in versions if v["version"] == version_a), None)
    vb = next((v for v in versions if v["version"] == version_b), None)
    if not va or not vb:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    diff = list(difflib.unified_diff(
        va["content"].splitlines(), vb["content"].splitlines(),
        fromfile=f"v{version_a}", tofile=f"v{version_b}", lineterm="",
    ))
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    return {
        "template_id": template_id, "version_a": version_a, "version_b": version_b,
        "diff": diff[:100], "added_lines": added, "removed_lines": removed,
        "similarity": difflib.SequenceMatcher(None, va["content"], vb["content"]).ratio(),
    }


@router.post("/{template_id}/test")
async def test_template(template_id: str, req: TemplateTestRequest):
    template = _templates.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    if req.version:
        versions = _template_versions.get(template_id, [])
        ve = next((v for v in versions if v["version"] == req.version), None)
        content = ve["content"] if ve else template["content"]
    else:
        content = template["content"]
    rendered = content
    for vn, vv in req.variables.items():
        rendered = rendered.replace("{{" + vn + "}}", str(vv))
    unreplaced = re.findall(r'\{\{(\w+)\}\}', rendered)
    return {
        "template_id": template_id, "version": req.version or template["current_version"],
        "original": content, "rendered": rendered,
        "variables_used": list(req.variables.keys()),
        "unreplaced_variables": unreplaced,
        "character_count": len(rendered), "token_estimate": len(rendered) // 4,
    }
