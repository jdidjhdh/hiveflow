"""Tests for hiveflow.memory_manager module."""

from hiveflow.memory_manager import LongTermMemory, MemoryEntry, MemoryManager, ShortTermMemory


class TestShortTermMemory:
    def test_add_and_get_recent(self):
        mem = ShortTermMemory(max_entries=10)
        mem.add("hello", role="user")
        mem.add("hi there", role="assistant")

        recent = mem.get_recent(1)
        assert len(recent) == 1
        assert recent[0].content == "hi there"
        assert recent[0].role == "assistant"

    def test_max_entries_eviction(self):
        mem = ShortTermMemory(max_entries=2)
        mem.add("first")
        mem.add("second")
        mem.add("third")

        assert mem.count_entries() == 2
        assert mem.get_recent(10)[0].content == "second"

    def test_get_as_messages_with_system(self):
        mem = ShortTermMemory()
        mem.add("question", role="user")
        messages = mem.get_as_messages(system_prompt="You are helpful")
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add("x")
        mem.clear()
        assert mem.count_entries() == 0


class TestLongTermMemoryFallback:
    """LongTermMemory without Chroma uses in-memory fallback search."""

    @staticmethod
    def _fallback_ltm(name: str) -> LongTermMemory:
        ltm = LongTermMemory(collection_name=name)
        ltm._available = False
        return ltm

    def test_add_and_search_fallback(self):
        ltm = self._fallback_ltm("test_fallback_mem")
        ltm.add("HiveFlow multi-agent orchestration engine", metadata={"topic": "hiveflow"})
        ltm.add("Unrelated cooking recipe for pasta", metadata={"topic": "food"})

        hits = ltm.search("HiveFlow agent", n_results=2)
        assert len(hits) >= 1
        assert "HiveFlow" in hits[0]["content"]

    def test_count_and_clear_fallback(self):
        ltm = self._fallback_ltm("test_clear_mem")
        ltm.add("entry one", metadata={"n": "1"})
        ltm.add("entry two", metadata={"n": "2"})
        assert ltm.count() == 2
        ltm.clear()
        assert ltm.count() == 0

    def test_delete_fallback(self):
        ltm = self._fallback_ltm("test_delete_mem")
        entry_id = ltm.add("to remove", metadata={"n": "1"})
        assert ltm.delete(entry_id) in (True, False)


class TestMemoryManager:
    def test_user_and_assistant_messages(self):
        mgr = MemoryManager(session_id="sess-1")
        user = mgr.add_user_message("Hello")
        assistant = mgr.add_assistant_message("Hi!", metadata={"persist": True})

        assert isinstance(user, MemoryEntry)
        assert assistant.role == "assistant"
        assert mgr.get_recent(2)[0].content == "Hello"

    def test_add_observation(self):
        mgr = MemoryManager()
        entry = mgr.add_observation("tool returned data")
        assert entry.role == "observation"

    def test_get_context(self):
        mgr = MemoryManager()
        mgr.add_user_message("Q1")
        messages = mgr.get_context(system_prompt="sys")
        assert messages[0].content == "sys"
        assert any(m.content == "Q1" for m in messages)

    def test_build_context_with_retrieval(self):
        mgr = MemoryManager(session_id="retrieval-test")
        mgr.add_user_message("We discussed HiveFlow blackboard permissions")
        mgr.short_term.clear()
        mgr.long_term._available = False
        mgr.long_term.add("HiveFlow blackboard uses prefix patterns", metadata={"topic": "bb"})

        messages = mgr.build_context_with_retrieval(
            query="blackboard permissions",
            system_prompt="Base",
            recent_n=5,
            memory_n=2,
        )
        assert messages[0].role == "system"
        assert "Relevant past context" in messages[0].content
        assert any(m.content == "Base" for m in messages)

    def test_clear_session(self):
        mgr = MemoryManager(session_id="clear-test")
        mgr.add_user_message("temp")
        mgr.long_term.add("long")
        mgr.clear_session()
        assert mgr.short_term.count_entries() == 0
        assert mgr.long_term.count() == 0

    def test_search_memory(self):
        mgr = MemoryManager(session_id="search-test")
        mgr.add_user_message("checkpoint time travel feature")
        results = mgr.search_memory("checkpoint", n_results=3)
        assert isinstance(results, list)
