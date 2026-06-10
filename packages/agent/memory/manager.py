import uuid
import time
import asyncio
from typing import Any, List, Dict, Optional
try:
    from ..core.secure_blackboard import SecureBlackboard
except ImportError:
    from core.secure_blackboard import SecureBlackboard
try:
    from .vector_store import VectorStore, MemoryItem
except ImportError:
    from memory.vector_store import VectorStore, MemoryItem


class MemoryManager:
    def __init__(self, blackboard: SecureBlackboard, vector_store: VectorStore, short_term_limit=10):
        self.bb = blackboard
        self.vs = vector_store
        self.short_term_limit = short_term_limit
        self.short_term: List[Dict[str, str]] = []

    def add_to_short_term(self, role: str, content: str):
        self.short_term.append({"role": role, "content": content})
        max_messages = self.short_term_limit * 2
        if len(self.short_term) > max_messages:
            self.short_term = self.short_term[-max_messages:]

    def get_short_term(self) -> List[Dict[str, str]]:
        return self.short_term.copy()

    async def save_work_memory(self, key, value, ttl=None):
        await self.bb.sys_put(key, value, ttl)

    async def load_work_memory(self, key):
        return await self.bb.sys_get(key)

    async def save_long_term(self, content, metadata=None, ttl=None):
        doc_id = str(uuid.uuid4())
        meta = metadata or {}
        meta["timestamp"] = time.time()
        await self.vs.add_texts([content], metadatas=[meta], ids=[doc_id])
        await self.bb.sys_put(f"lmt:{doc_id}", {"content": content, "metadata": meta}, ttl)

    async def recall_long_term(self, query, k=5):
        return await self.vs.similarity_search(query, k)

    async def summarize_and_remember(self, conversation_id, llm):
        if not self.short_term:
            return
        convo = "\n".join([f"{t['role']}: {t['content']}" for t in self.short_term])
        summary = await llm.complete([
            {"role": "system", "content": "Summarize the conversation, preserving key info, intent and outcomes."},
            {"role": "user", "content": convo}
        ])
        await self.save_long_term(summary, metadata={"conversation_id": conversation_id, "type": "summary"})
        self.short_term.clear()
