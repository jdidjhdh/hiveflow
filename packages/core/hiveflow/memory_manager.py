"""HiveFlow - MemoryManager

Manages short-term memory (conversation history) and optional long-term memory
via Chroma vector storage for semantic retrieval.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from . import LLMMessage
except ImportError:
    from hiveflow import LLMMessage

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry."""

    content: str
    role: str  # "user", "assistant", "system", "observation"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ========== Short-Term Memory ==========


class ShortTermMemory:
    """In-memory conversation/task history with configurable size limits."""

    def __init__(self, max_entries: int = 50, max_tokens: int = 8000):
        self.max_entries = max_entries
        self.max_tokens = max_tokens
        self.entries: list[MemoryEntry] = []
        self._total_tokens = 0

    def add(self, content: str, role: str = "user", metadata: dict[str, Any] | None = None) -> MemoryEntry:
        entry = MemoryEntry(content=content, role=role, metadata=metadata or {})
        self.entries.append(entry)
        self._total_tokens += self._count_tokens(content)

        # Enforce limits
        while len(self.entries) > self.max_entries:
            removed = self.entries.pop(0)
            self._total_tokens -= self._count_tokens(removed.content)

        while self._total_tokens > self.max_tokens and self.entries:
            removed = self.entries.pop(0)
            self._total_tokens -= self._count_tokens(removed.content)

        return entry

    def get_recent(self, n: int = 10) -> list[MemoryEntry]:
        return self.entries[-n:]

    def get_as_messages(self, system_prompt: str = "") -> list[LLMMessage]:
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        for entry in self.entries:
            messages.append(LLMMessage(role=entry.role, content=entry.content))
        return messages

    def clear(self):
        self.entries.clear()
        self._total_tokens = 0

    def count_entries(self) -> int:
        return len(self.entries)

    @staticmethod
    def _count_tokens(text: str) -> int:
        """Rough token count: ~4 chars per token for English."""
        return max(1, len(text) // 4)


# ========== Long-Term Memory (Chroma-backed) ==========


class LongTermMemory:
    """Vector-based long-term memory using Chroma for semantic retrieval.

    Falls back to keyword-based search if Chroma is not available.
    """

    def __init__(self, collection_name: str = "hiveflow_memory", persist_dir: str | None = None):
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self._available = False
        self._collection = None
        self._fallback_store: list[MemoryEntry] = []

        # Try to initialize Chroma
        try:
            import threading

            import chromadb

            init_result = [None, None]

            def _init():
                try:
                    if persist_dir:
                        client = chromadb.PersistentClient(path=persist_dir)
                    else:
                        client = chromadb.Client()
                    collection = client.get_or_create_collection(
                        name=collection_name,
                        metadata={"hnsw:space": "cosine"},
                    )
                    init_result[0] = collection
                    init_result[1] = True
                except Exception as e:
                    init_result[1] = e

            t = threading.Thread(target=_init, daemon=True)
            t.start()
            t.join(timeout=3.0)  # 3-second timeout for Chroma init

            if init_result[0] and init_result[1] is True:
                self._collection = init_result[0]
                self._available = True
                logger.info(f"Chroma long-term memory initialized: {collection_name}")
            else:
                err = init_result[1] if isinstance(init_result[1], Exception) else None
                if err:
                    logger.warning(f"Chroma init failed: {err}, using fallback")
                else:
                    logger.warning("Chroma init timed out, using fallback")
        except ImportError:
            logger.info("Chroma not available, using fallback keyword search for long-term memory")

    def add(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        entry_id = f"mem_{time.time()}"
        entry = MemoryEntry(content=content, role="memory", metadata=metadata or {})

        if self._available and self._collection:
            try:
                self._collection.add(
                    documents=[content],
                    ids=[entry_id],
                    metadatas=[metadata or {}],
                )
            except Exception as e:
                logger.warning(f"Failed to add to Chroma: {e}")
                self._fallback_store.append(entry)
        else:
            self._fallback_store.append(entry)

        return entry_id

    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        if self._available and self._collection:
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=n_results,
                )
                if results["ids"] and results["ids"][0]:
                    return [
                        {"content": doc, "metadata": meta, "id": entry_id}
                        for doc, meta, entry_id in zip(
                            results["documents"][0],
                            results["metadatas"][0],
                            results["ids"][0],
                        )
                    ]
            except Exception as e:
                logger.warning(f"Chroma search failed: {e}")

        # Fallback: keyword-based search
        return self._fallback_search(query, n_results)

    def _fallback_search(self, query: str, n_results: int) -> list[dict[str, Any]]:
        """Simple keyword-based search as fallback."""
        query_lower = query.lower()
        scored = []
        for entry in self._fallback_store:
            score = query_lower.count(query_lower)  # Simple match count
            if query_lower in entry.content.lower():
                score = entry.content.lower().count(query_lower) + 1
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        return [{"content": entry.content, "metadata": entry.metadata, "id": ""} for _, entry in scored[:n_results]]

    def delete(self, entry_id: str) -> bool:
        if self._available and self._collection:
            try:
                self._collection.delete(ids=[entry_id])
                return True
            except Exception as e:
                logger.warning(f"Failed to delete from Chroma: {e}")

        # Fallback
        original_len = len(self._fallback_store)
        self._fallback_store = [e for e in self._fallback_store if f"mem_{e.timestamp}" != entry_id]
        return len(self._fallback_store) < original_len

    def clear(self):
        if self._available and self._collection:
            try:
                ids = self._collection.get()["ids"]
                if ids:
                    self._collection.delete(ids=ids)
            except Exception as e:
                logger.warning(f"Failed to clear Chroma: {e}")
        self._fallback_store.clear()

    def count(self) -> int:
        if self._available and self._collection:
            try:
                return self._collection.count()
            except Exception:
                pass
        return len(self._fallback_store)


# ========== MemoryManager (unified interface) ==========


class MemoryManager:
    """Unified memory manager combining short-term and long-term memory."""

    def __init__(
        self,
        session_id: str = "default",
        short_term_max_entries: int = 50,
        short_term_max_tokens: int = 8000,
        long_term_persist_dir: str | None = None,
        long_term_collection: str = "hiveflow_memory",
    ):
        self.session_id = session_id
        self.short_term = ShortTermMemory(
            max_entries=short_term_max_entries,
            max_tokens=short_term_max_tokens,
        )
        self.long_term = LongTermMemory(
            collection_name=f"{long_term_collection}_{session_id}",
            persist_dir=long_term_persist_dir,
        )

    def add_user_message(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        entry = self.short_term.add(content, "user", metadata)
        # Also store in long-term memory for future retrieval
        self.long_term.add(content, {"role": "user", **{k: str(v) for k, v in (metadata or {}).items()}})
        return entry

    def add_assistant_message(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        entry = self.short_term.add(content, "assistant", metadata)
        # Store important assistant responses in long-term memory
        if metadata and metadata.get("persist", False):
            self.long_term.add(content, {"role": "assistant", **{k: str(v) for k, v in metadata.items()}})
        return entry

    def add_observation(self, content: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        return self.short_term.add(content, "observation", metadata)

    def get_context(self, system_prompt: str = "", recent_n: int = 10) -> list[LLMMessage]:
        return self.short_term.get_as_messages(system_prompt)

    def search_memory(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        return self.long_term.search(query, n_results)

    def get_recent(self, n: int = 10) -> list[MemoryEntry]:
        return self.short_term.get_recent(n)

    def clear_session(self):
        self.short_term.clear()
        self.long_term.clear()

    def build_context_with_retrieval(
        self,
        query: str,
        system_prompt: str = "",
        recent_n: int = 10,
        memory_n: int = 3,
    ) -> list[LLMMessage]:
        """Build context combining recent conversation with relevant long-term memories."""
        messages = self.short_term.get_as_messages(system_prompt)

        # Search long-term memory for relevant context
        memories = self.long_term.search(query, n_results=memory_n)
        if memories:
            memory_context = "\n\nRelevant past context:\n"
            for m in memories:
                memory_context += f"- {m['content']}\n"
            # Inject memory context as a system message at the beginning
            messages.insert(0, LLMMessage(role="system", content=memory_context))

        return messages
