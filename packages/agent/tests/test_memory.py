import pytest
import asyncio
from memory.manager import MemoryManager
from memory.vector_store import ChromaVectorStore
from core.secure_blackboard import SecureBlackboard, MemoryBlackboard


async def simple_embedding_fn(texts):
    """Simple hash-based embedding function that avoids network downloads."""
    embeddings = []
    for text in texts:
        embedding = [float(hash(text + str(i)) % 10000) / 10000.0 for i in range(384)]
        embeddings.append(embedding)
    return embeddings


@pytest.fixture
def mem_manager(tmp_path):
    bb = SecureBlackboard(MemoryBlackboard())
    vs = ChromaVectorStore(path=str(tmp_path / "chroma"), embedding_fn=simple_embedding_fn)
    return MemoryManager(bb, vs, short_term_limit=5)


@pytest.mark.asyncio
async def test_short_term_memory(mem_manager):
    mem_manager.add_to_short_term("user", "Hello")
    mem_manager.add_to_short_term("assistant", "Hi there")
    st = mem_manager.get_short_term()
    assert len(st) == 2
    assert st[0]["role"] == "user"


@pytest.mark.asyncio
async def test_short_term_trimming():
    bb = SecureBlackboard(MemoryBlackboard())
    vs = ChromaVectorStore(path="./tmp_chroma_trim", embedding_fn=simple_embedding_fn)
    mm = MemoryManager(bb, vs, short_term_limit=2)
    for i in range(10):
        mm.add_to_short_term("user", f"message_{i}")
    st = mm.get_short_term()
    assert len(st) <= 4  # short_term_limit * 2


@pytest.mark.asyncio
async def test_work_memory(mem_manager):
    await mem_manager.save_work_memory("work:key", {"data": "test"})
    val = await mem_manager.load_work_memory("work:key")
    assert val == {"data": "test"}


@pytest.mark.asyncio
async def test_long_term_memory(mem_manager):
    await mem_manager.save_long_term("Python is a programming language", metadata={"category": "tech"})
    items = await mem_manager.recall_long_term("programming", k=1)
    assert len(items) >= 1
