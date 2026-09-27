"""
Semantic Cache for LLM responses.

Provides caching based on semantic similarity of prompts using embeddings.
Uses LRU eviction with TTL support.
"""

import time
from collections import OrderedDict
from typing import Callable, Optional

import numpy as np


class SemanticCache:
    """
    Semantic cache for LLM responses using embedding similarity.

    Features:
    - LRU eviction when capacity is reached
    - TTL-based expiration
    - Semantic similarity matching using cosine similarity

    Args:
        embed_fn: Async function to generate embeddings from text.
            Should accept list of strings and return list of embedding vectors.
        similarity_threshold: Minimum cosine similarity to consider a match (default: 0.95)
        ttl_seconds: Time-to-live for cache entries in seconds (default: 600)
        max_capacity: Maximum number of entries in cache (default: 1000)
    """

    def __init__(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]],
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 600,
        max_capacity: int = 1000,
    ):
        self.embed_fn = embed_fn
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_capacity = max_capacity

        # OrderedDict for LRU: key -> (embedding, response, timestamp)
        self._cache: OrderedDict[str, tuple[list[float], dict, float]] = OrderedDict()

    async def get(self, prompt: str) -> tuple[dict, bool]:
        """
        Retrieve cached response for semantically similar prompt.

        Args:
            prompt: Input prompt to search in cache

        Returns:
            Tuple of (response_dict, found_flag)
            - response_dict: Cached response if found, empty dict otherwise
            - found_flag: True if semantically similar prompt found in cache
        """
        # Generate embedding for the query prompt
        embeddings = await self.embed_fn([prompt])
        if not embeddings:
            return {}, False
        query_embedding = embeddings[0]

        current_time = time.monotonic()

        # Search for semantically similar prompt in cache
        for key, (cached_embedding, response, timestamp) in list(self._cache.items()):
            # Check TTL
            if current_time - timestamp > self.ttl_seconds:
                # Remove expired entry
                del self._cache[key]
                continue

            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, cached_embedding)

            if similarity >= self.similarity_threshold:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                return response, True

        return {}, False

    async def set(self, prompt: str, response: dict) -> None:
        """
        Store response in cache for the given prompt.

        Args:
            prompt: Input prompt
            response: Response dictionary to cache
        """
        # Generate embedding for the prompt
        embeddings = await self.embed_fn([prompt])
        if not embeddings:
            return
        embedding = embeddings[0]

        current_time = time.monotonic()

        # Remove oldest entry if at capacity (LRU eviction)
        if len(self._cache) >= self.max_capacity:
            self._cache.popitem(last=False)

        # Store in cache (will be added at the end as most recently used)
        self._cache[prompt] = (embedding, response, current_time)

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between 0 and 1
        """
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()

    def size(self) -> int:
        """Return current number of entries in cache."""
        return len(self._cache)

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        current_time = time.monotonic()
        expired_keys = [
            key
            for key, (_, _, timestamp) in self._cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)