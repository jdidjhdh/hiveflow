"""HiveFlow Studio - 知识库 (RAG) API

提供知识库的 REST API，支持：
- 知识库 CRUD
- 文档上传/删除/列表
- 查询和搜索
- 多模态内容添加（图片/音频）
"""
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.core.engine_service import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ======================== Models ========================

class KBCreateRequest(BaseModel):
    kb_id: str
    name: str
    description: str = ""


class KBUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DocumentAddRequest(BaseModel):
    content: str
    doc_type: str = "text"
    metadata: dict = Field(default_factory=dict)


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    metadata_filter: Optional[dict] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    metadata_filter: Optional[dict] = None


# ======================== Routes ========================

@router.get("")
async def list_knowledge_bases():
    """列出所有知识库"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    kbs = await kb_manager.list_kbs()
    return {"knowledge_bases": [
        {
            "kb_id": kb.kb_id,
            "name": kb.name,
            "description": kb.description,
            "doc_count": kb.doc_count,
            "vector_store": kb.vector_store_type,
            "created_at": kb.created_at,
        }
        for kb in kbs
    ]}


@router.post("")
async def create_knowledge_base(req: KBCreateRequest):
    """创建知识库"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    await kb_manager.create_kb(req.kb_id, req.name, req.description)
    return {"kb_id": req.kb_id, "name": req.name, "status": "created"}


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    """删除知识库"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    try:
        deleted = await kb_manager.delete_kb(kb_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
        return {"kb_id": kb_id, "status": "deleted"}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")


@router.get("/{kb_id}")
async def get_knowledge_base(kb_id: str):
    """获取知识库详情"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    kb = kb_manager.get_kb(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
    return {
        "kb_id": kb.kb_id,
        "name": kb.name,
        "description": kb.description,
        "doc_count": kb.doc_count,
        "vector_store": kb.vector_store_type,
        "created_at": kb.created_at,
    }


@router.put("/{kb_id}")
async def update_knowledge_base(kb_id: str, req: KBUpdateRequest):
    """更新知识库名称与描述"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    kb = kb_manager.get_kb(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
    if req.name is not None:
        kb.name = req.name
    if req.description is not None:
        kb.description = req.description
    return {"kb_id": kb_id, "name": kb.name, "description": kb.description, "status": "updated"}


@router.post("/{kb_id}/query")
async def query_knowledge_base(kb_id: str, req: QueryRequest):
    """Query knowledge base (RAG retrieval + answer assembly)."""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    try:
        result = await kb_manager.query(
            kb_id,
            req.query,
            top_k=req.top_k,
            filters=req.metadata_filter,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "query": req.query,
        "answer": result.answer,
        "context": result.context,
        "latency_ms": result.latency_ms,
        "results": [
            {
                "content": r.chunk.content,
                "score": r.score,
                "metadata": r.metadata,
                "doc_id": r.chunk.doc_id,
            }
            for r in result.sources
        ],
    }


@router.post("/{kb_id}/search")
async def search_knowledge_base(kb_id: str, req: SearchRequest):
    """Search knowledge base (retrieval only)."""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    try:
        results = await kb_manager.search(
            kb_id,
            req.query,
            top_k=req.top_k,
            filters=req.metadata_filter,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "query": req.query,
        "results": [
            {
                "content": r.chunk.content,
                "score": r.score,
                "metadata": r.metadata,
                "doc_id": r.chunk.doc_id,
            }
            for r in results
        ],
    }


@router.post("/{kb_id}/documents")
async def add_document(kb_id: str, req: DocumentAddRequest):
    """添加文档到知识库"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    from hiveflow.rag import Document, DocumentType

    doc_type = DocumentType(req.doc_type)
    doc = Document(
        doc_id=Document.compute_doc_id(req.content, req.doc_type),
        content=req.content,
        doc_type=doc_type,
        metadata=req.metadata,
    )
    ids = await kb_manager.add_document(kb_id, doc)
    return {"doc_ids": ids, "status": "added"}


@router.post("/{kb_id}/documents/upload")
async def upload_document(kb_id: str, file: UploadFile = File(...), chunk_strategy: str = Form("recursive")):
    """上传文件到知识库"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()

    content = await file.read()
    text = content.decode("utf-8")

    from hiveflow.rag import Document, DocumentType

    doc = Document(
        doc_id=Document.compute_doc_id(text, "text"),
        content=text,
        doc_type=DocumentType.TEXT,
        metadata={"filename": file.filename, "chunk_strategy": chunk_strategy},
    )
    ids = await kb_manager.add_document(kb_id, doc)
    return {"doc_ids": ids, "filename": file.filename, "status": "uploaded"}


@router.get("/{kb_id}/documents")
async def list_documents(kb_id: str):
    """列出知识库中的所有文档"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    kb = kb_manager.get_kb(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")

    return {
        "kb_id": kb_id,
        "doc_count": kb.doc_count,
        "documents": list(kb.document_store),
    }


@router.delete("/{kb_id}/documents/{doc_id}")
async def remove_document(kb_id: str, doc_id: str):
    """从知识库删除文档"""
    engine = get_engine()
    kb_manager = engine.get_kb_manager()
    await kb_manager.remove_document(kb_id, doc_id)
    return {"doc_id": doc_id, "status": "removed"}
