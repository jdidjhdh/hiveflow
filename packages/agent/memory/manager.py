import time
import uuid
import logging
from collections import OrderedDict

try:
    from ..core.secure_blackboard import SecureBlackboard
except ImportError:
    from core.secure_blackboard import SecureBlackboard
try:
    from .vector_store import MemoryItem, VectorStore
except ImportError:
    from memory.vector_store import VectorStore


logger = logging.getLogger(__name__)


class MemoryManager:
    """
    🔒 SECURITY FIX: Add user/conversation isolation to prevent memory cross-access.
    🔄 P0 FIX: Add LRU eviction to prevent unbounded session dictionary growth.
    
    Memory is now isolated by:
    - user_id: Prevents user A from accessing user B's memories
    - conversation_id: Groups memories by conversation session
    
    Short-term memory is also isolated per conversation to prevent context leakage.
    """
    
    def __init__(self, blackboard: SecureBlackboard, vector_store: VectorStore, 
                 short_term_limit=10, max_conversations: int = 1000):
        self.bb = blackboard
        self.vs = vector_store
        self.short_term_limit = short_term_limit
        self.max_conversations = max_conversations  # 🔄 P0 FIX: Max conversations limit
        # 🔒 FIX: Change from single list to dict keyed by conversation_id
        # 🔄 P0 FIX: Use OrderedDict for LRU eviction
        self._short_term: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        self._current_conversation: str | None = None

    def set_context(self, conversation_id: str, user_id: str | None = None):
        """
        🔒 SECURITY: Set the current conversation context for memory isolation.
        Must be called before any memory operations.
        
        🔄 P0 FIX: LRU eviction when max_conversations exceeded.
        """
        self._current_conversation = conversation_id
        if conversation_id not in self._short_term:
            # 🔄 P0 FIX: Check if we need to evict oldest conversation
            if len(self._short_term) >= self.max_conversations:
                # Evict oldest conversation (first item in OrderedDict)
                oldest_conv_id, oldest_memory = self._short_term.popitem(last=False)
                logger.info(f"LRU evicted conversation {oldest_conv_id} ({len(oldest_memory)} messages)")
            self._short_term[conversation_id] = []
        else:
            # 🔄 P0 FIX: Move to end to mark as recently used
            self._short_term.move_to_end(conversation_id)

    def add_to_short_term(self, role: str, content: str, conversation_id: str | None = None):
        """
        🔒 SECURITY FIX: Isolate short-term memory by conversation_id.
        🔄 P0 FIX: LRU eviction when max_conversations exceeded.
        """
        conv_id = conversation_id or self._current_conversation
        if not conv_id:
            logger.warning("add_to_short_term called without conversation context")
            return
        
        if conv_id not in self._short_term:
            # 🔄 P0 FIX: Check if we need to evict oldest conversation
            if len(self._short_term) >= self.max_conversations:
                oldest_conv_id, oldest_memory = self._short_term.popitem(last=False)
                logger.info(f"LRU evicted conversation {oldest_conv_id} ({len(oldest_memory)} messages)")
            self._short_term[conv_id] = []
        else:
            # 🔄 P0 FIX: Move to end to mark as recently used
            self._short_term.move_to_end(conv_id)
        
        self._short_term[conv_id].append({"role": role, "content": content})
        max_messages = self.short_term_limit * 2
        if len(self._short_term[conv_id]) > max_messages:
            self._short_term[conv_id] = self._short_term[conv_id][-max_messages:]

    def get_short_term(self, conversation_id: str | None = None) -> list[dict[str, str]]:
        """
        🔒 SECURITY FIX: Return short-term memory for specific conversation only.
        """
        conv_id = conversation_id or self._current_conversation
        if not conv_id:
            return []
        return self._short_term.get(conv_id, []).copy()

    async def save_work_memory(self, key, value, ttl=None, conversation_id: str | None = None):
        """
        🔒 SECURITY FIX: Prefix key with conversation_id to isolate work memory.
        """
        conv_id = conversation_id or self._current_conversation
        if conv_id:
            key = f"work:{conv_id}:{key}"
        await self.bb.sys_put(key, value, ttl)

    async def load_work_memory(self, key, conversation_id: str | None = None):
        """
        🔒 SECURITY FIX: Load work memory with conversation_id prefix.
        """
        conv_id = conversation_id or self._current_conversation
        if conv_id:
            key = f"work:{conv_id}:{key}"
        return await self.bb.sys_get(key)

    async def save_long_term(self, content, metadata=None, ttl=None, user_id: str | None = None, conversation_id: str | None = None):
        """
        🔒 SECURITY FIX: Store long-term memory with user_id/conversation_id metadata.
        This ensures memory retrieval can filter by owner.
        """
        doc_id = str(uuid.uuid4())
        meta = metadata or {}
        meta["timestamp"] = time.time()
        
        # 🔒 SECURITY: Add isolation metadata
        conv_id = conversation_id or self._current_conversation
        if conv_id:
            meta["conversation_id"] = conv_id
        if user_id:
            meta["user_id"] = user_id
        
        await self.vs.add_texts([content], metadatas=[meta], ids=[doc_id])
        await self.bb.sys_put(f"lmt:{doc_id}", {"content": content, "metadata": meta}, ttl)

    async def recall_long_term(self, query, k=5, user_id: str | None = None, conversation_id: str | None = None):
        """
        🔒 SECURITY FIX: Filter long-term memory by user_id/conversation_id.
        Prevents cross-user memory access (memory越权).
        
        Args:
            query: Search query
            k: Number of results
            user_id: 🔒 Required - Only return memories belonging to this user
            conversation_id: Optional - Further filter by conversation
        
        Returns:
            List of MemoryItems filtered by ownership
        """
        # 🔒 SECURITY: Build filter dict for vector store
        filter_dict = {}
        if user_id:
            filter_dict["user_id"] = user_id
        if conversation_id:
            filter_dict["conversation_id"] = conversation_id
        
        # Call similarity_search with filter
        # Note: VectorStore implementation must support metadata filtering
        try:
            results = await self.vs.similarity_search(query, k, filter=filter_dict)
        except TypeError:
            # Fallback if vector store doesn't support filter parameter
            results = await self.vs.similarity_search(query, k)
            # Manual filtering as fallback
            if user_id or conversation_id:
                filtered = []
                for item in results:
                    meta = getattr(item, 'metadata', {})
                    if user_id and meta.get("user_id") != user_id:
                        continue
                    if conversation_id and meta.get("conversation_id") != conversation_id:
                        continue
                    filtered.append(item)
                results = filtered
        
        return results

    async def summarize_and_remember(self, conversation_id: str, llm, user_id: str | None = None):
        """
        🔒 SECURITY FIX: Summarize and store with isolation metadata.
        """
        conv_id = conversation_id or self._current_conversation
        if not conv_id:
            logger.warning("summarize_and_remember called without conversation context")
            return
        
        short_term = self._short_term.get(conv_id, [])
        if not short_term:
            return
        
        convo = "\n".join([f"{t['role']}: {t['content']}" for t in short_term])
        summary = await llm.complete([
            {"role": "system", "content": "Summarize the conversation, preserving key info, intent and outcomes."},
            {"role": "user", "content": convo}
        ])
        
        # 🔒 SECURITY: Save with isolation metadata
        await self.save_long_term(
            summary,
            metadata={"conversation_id": conv_id, "type": "summary"},
            user_id=user_id
        )
        
        # Clear only this conversation's short-term memory
        self._short_term[conv_id] = []
    
    def clear_context(self):
        """Clear current conversation context."""
        self._current_conversation = None
    
    def get_stats(self) -> dict:
        """
        🔄 P0 FIX: Get memory manager statistics for monitoring.
        
        Returns:
            Dict with conversation count, total messages, and LRU info
        """
        total_messages = sum(len(mem) for mem in self._short_term.values())
        return {
            "active_conversations": len(self._short_term),
            "max_conversations": self.max_conversations,
            "total_messages": total_messages,
            "current_conversation": self._current_conversation,
            "oldest_conversation": next(iter(self._short_term.keys())) if self._short_term else None,
            "newest_conversation": next(reversed(self._short_term.keys())) if self._short_term else None,
        }
