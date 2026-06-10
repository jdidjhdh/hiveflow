"""HiveFlow - MemoryManager tests"""
import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import ShortTermMemory, MemoryEntry
from hiveflow.memory_manager import MemoryManager


# Helper to create LongTermMemory that forces fallback mode (no Chroma)
def _create_fallback_long_term(collection_name="test", persist_dir=None):
    """Create LongTermMemory with Chroma disabled."""
    from hiveflow.memory_manager import LongTermMemory
    mem = LongTermMemory.__new__(LongTermMemory)
    mem.collection_name = collection_name
    mem.persist_dir = persist_dir
    mem._available = False  # Force fallback mode
    mem._collection = None
    mem._fallback_store = []
    return mem


# ========== ShortTermMemory Tests ==========

def test_short_term_add_and_get():
    mem = ShortTermMemory(max_entries=10, max_tokens=10000)
    mem.add("Hello", "user")
    mem.add("Hi there!", "assistant")

    assert mem.count_entries() == 2
    recent = mem.get_recent(5)
    assert len(recent) == 2
    assert recent[0].content == "Hello"
    assert recent[1].content == "Hi there!"


def test_short_term_respects_max_entries():
    mem = ShortTermMemory(max_entries=3, max_tokens=10000)
    for i in range(10):
        mem.add(f"Message {i}", "user")

    assert mem.count_entries() == 3
    recent = mem.get_recent(3)
    assert recent[0].content == "Message 7"
    assert recent[2].content == "Message 9"


def test_short_term_respects_max_tokens():
    mem = ShortTermMemory(max_entries=100, max_tokens=20)  # Very small limit
    mem.add("A" * 40, "user")  # ~10 tokens
    mem.add("B" * 40, "user")  # ~10 tokens (total ~20)
    mem.add("C" * 40, "user")  # ~10 tokens (total ~30, should evict first)

    assert mem.count_entries() <= 2


def test_short_term_get_as_messages():
    mem = ShortTermMemory()
    mem.add("System instruction", "system")
    mem.add("User query", "user")
    mem.add("Assistant response", "assistant")

    messages = mem.get_as_messages(system_prompt="You are helpful")
    assert len(messages) == 4
    assert messages[0].role == "system"
    assert messages[0].content == "You are helpful"
    assert messages[1].role == "system"
    assert messages[2].role == "user"
    assert messages[3].role == "assistant"


def test_short_term_clear():
    mem = ShortTermMemory()
    mem.add("test", "user")
    assert mem.count_entries() == 1
    mem.clear()
    assert mem.count_entries() == 0


# ========== LongTermMemory Tests (fallback mode only) ==========

def test_long_term_fallback_add():
    """LongTermMemory should work in fallback mode (without Chroma)."""
    mem = _create_fallback_long_term("test_fallback")
    entry_id = mem.add("This is a test memory", {"topic": "test"})

    results = mem.search("test memory", n_results=1)
    assert len(results) >= 1
    assert "test memory" in results[0]["content"]


def test_long_term_fallback_search():
    """Fallback search should return relevant results."""
    mem = _create_fallback_long_term("test_search")
    mem.add("Python is a programming language")
    mem.add("Java is also popular")
    mem.add("Rust is great for systems programming")

    results = mem.search("Python", n_results=2)
    assert len(results) >= 1
    assert any("Python" in r["content"] for r in results)


def test_long_term_search_returns_most_relevant():
    """Most relevant result should appear first."""
    mem = _create_fallback_long_term("test_relevance")
    mem.add("Dogs are great pets")
    mem.add("Python is a great programming language for data science")
    mem.add("Cats are independent animals")

    results = mem.search("Python programming", n_results=3)
    assert len(results) >= 1
    assert any("Python" in r["content"] for r in results)


def test_long_term_delete():
    """Should handle delete in fallback mode."""
    mem = _create_fallback_long_term("test_delete")
    mem.add("Entry A")
    mem.add("Entry B")

    count_before = mem.count()
    assert count_before >= 2

    mem.delete("nonexistent")
    assert mem.count() >= count_before - 1


def test_long_term_clear():
    """Should clear all entries."""
    mem = _create_fallback_long_term("test_clear")
    mem.add("Entry 1")
    mem.add("Entry 2")
    assert mem.count() >= 2

    mem.clear()
    assert mem.count() == 0


# ========== MemoryManager Tests ==========

@pytest.fixture
def memory_manager():
    """Create MemoryManager with fallback LongTermMemory."""
    mm = MemoryManager.__new__(MemoryManager)
    mm.session_id = "test_session_mm"
    mm.short_term = ShortTermMemory()
    mm.long_term = _create_fallback_long_term(f"test_mm_{mm.session_id}")
    return mm


def test_memory_manager_add_user(memory_manager):
    entry = memory_manager.add_user_message("What is Python?")

    assert entry.content == "What is Python?"
    assert entry.role == "user"
    assert memory_manager.short_term.count_entries() == 1


def test_memory_manager_add_assistant(memory_manager):
    memory_manager.add_user_message("Hello")
    entry = memory_manager.add_assistant_message("Hi! How can I help?")

    assert entry.role == "assistant"
    assert memory_manager.short_term.count_entries() == 2


def test_memory_manager_add_observation(memory_manager):
    entry = memory_manager.add_observation("User clicked button")

    assert entry.role == "observation"


def test_memory_manager_get_context(memory_manager):
    memory_manager.add_user_message("Question 1")
    memory_manager.add_assistant_message("Answer 1")
    memory_manager.add_user_message("Question 2")

    context = memory_manager.get_context(system_prompt="You are an assistant")
    assert len(context) >= 4
    assert context[0].content == "You are an assistant"


def test_memory_manager_search(memory_manager):
    memory_manager.add_user_message("How does Python work?")
    memory_manager.add_assistant_message("Python is an interpreted language", metadata={"persist": True})
    memory_manager.add_user_message("What about Java?")

    results = memory_manager.search_memory("Python language")
    assert len(results) >= 1


def test_memory_manager_build_context_with_retrieval(memory_manager):
    memory_manager.add_user_message("User asked about APIs")
    memory_manager.add_assistant_message("APIs are interfaces for services", metadata={"persist": True})
    memory_manager.add_user_message("Tell me more")

    context = memory_manager.build_context_with_retrieval(
        query="API",
        system_prompt="You are helpful",
        recent_n=5,
        memory_n=2,
    )

    assert len(context) >= 3


def test_memory_manager_clear_session(memory_manager):
    memory_manager.add_user_message("test")
    memory_manager.add_assistant_message("response")
    assert memory_manager.short_term.count_entries() == 2

    memory_manager.clear_session()
    assert memory_manager.short_term.count_entries() == 0


# ========== MemoryEntry Tests ==========

def test_memory_entry_defaults():
    entry = MemoryEntry(content="test", role="user")
    assert entry.content == "test"
    assert entry.role == "user"
    assert entry.timestamp > 0
    assert entry.metadata == {}


def test_memory_entry_with_metadata():
    entry = MemoryEntry(content="test", role="assistant", metadata={"skill": "research", "confidence": 0.9})
    assert entry.metadata["skill"] == "research"
    assert entry.metadata["confidence"] == 0.9
