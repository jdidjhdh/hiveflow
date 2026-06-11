"""Tests for hiveflow RAG module (KnowledgeBaseManager isolation)."""
import pytest

from hiveflow.rag import (
    Document,
    DocumentType,
    KnowledgeBaseManager,
    MemoryVectorStore,
)


@pytest.mark.asyncio
async def test_kb_isolation_default_per_kb_stores():
    """Each KB uses its own vector store by default; queries must not cross-contaminate."""
    mgr = KnowledgeBaseManager()

    await mgr.create_kb("kb_a", "KB A")
    await mgr.create_kb("kb_b", "KB B")

    doc_a = Document(
        doc_id="doc_a",
        content="Alpha secret keyword UNIQUE_ALPHA_TOKEN",
        doc_type=DocumentType.TEXT,
    )
    doc_b = Document(
        doc_id="doc_b",
        content="Beta secret keyword UNIQUE_BETA_TOKEN",
        doc_type=DocumentType.TEXT,
    )
    await mgr.add_document("kb_a", doc_a)
    await mgr.add_document("kb_b", doc_b)

    results_a = await mgr.search("kb_a", "UNIQUE_ALPHA_TOKEN")
    results_b = await mgr.search("kb_b", "UNIQUE_BETA_TOKEN")

    assert len(results_a) >= 1
    assert all("UNIQUE_ALPHA" in r.chunk.content for r in results_a)
    assert all("UNIQUE_BETA" not in r.chunk.content for r in results_a)

    assert len(results_b) >= 1
    assert all("UNIQUE_BETA" in r.chunk.content for r in results_b)
    assert all("UNIQUE_ALPHA" not in r.chunk.content for r in results_b)


@pytest.mark.asyncio
async def test_kb_delete_removes_vectors():
    """delete_kb removes indexed chunks so search returns empty."""
    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_del", "Delete Test")

    doc = Document(
        doc_id="d1",
        content="Ephemeral content for deletion test",
        doc_type=DocumentType.TEXT,
    )
    await mgr.add_document("kb_del", doc)
    assert len(await mgr.search("kb_del", "Ephemeral")) >= 1

    assert await mgr.delete_kb("kb_del")
    with pytest.raises(ValueError, match="not found"):
        await mgr.search("kb_del", "Ephemeral")


@pytest.mark.asyncio
async def test_kb_shared_store_uses_kb_id_filter():
    """Explicit shared vector store tags chunks with kb_id and filters on search."""
    shared = MemoryVectorStore()
    mgr = KnowledgeBaseManager(vector_store=shared)

    await mgr.create_kb("shared_a", "Shared A")
    await mgr.create_kb("shared_b", "Shared B")

    await mgr.add_document(
        "shared_a",
        Document(doc_id="sa", content="Shared store alpha marker", doc_type=DocumentType.TEXT),
    )
    await mgr.add_document(
        "shared_b",
        Document(doc_id="sb", content="Shared store beta marker", doc_type=DocumentType.TEXT),
    )

    hits_a = await mgr.search("shared_a", "alpha marker")
    hits_b = await mgr.search("shared_b", "beta marker")

    assert len(hits_a) >= 1
    assert all("alpha" in r.chunk.content.lower() for r in hits_a)
    assert all("beta" not in r.chunk.content.lower() for r in hits_a)

    assert len(hits_b) >= 1
    assert all("beta" in r.chunk.content.lower() for r in hits_b)


@pytest.mark.asyncio
async def test_kb_create_duplicate_raises():
    mgr = KnowledgeBaseManager()
    await mgr.create_kb("dup", "First")
    with pytest.raises(ValueError, match="already exists"):
        await mgr.create_kb("dup", "Second")
