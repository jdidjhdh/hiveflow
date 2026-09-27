import asyncio
import base64
import json
import logging
import math
import os
import pickle
import re
import sys
import time
import zlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from fnmatch import fnmatch
from typing import Any

try:
    from . import Capability
except ImportError:
    from hiveflow import Capability

logger = logging.getLogger(__name__)


class ObjectTooLargeError(Exception):
    """
    对象过大错误

    当尝试存储超过 max_object_size 限制的对象时抛出。
    """

    def __init__(self, message: str, object_size: int, max_size: int, key: str | None = None):
        super().__init__(message)
        self.object_size = object_size
        self.max_size = max_size
        self.key = key

    def __str__(self) -> str:
        size_mb = self.object_size / (1024 * 1024)
        max_mb = self.max_size / (1024 * 1024)
        if self.key:
            return f"{super().__str__()} Key: '{self.key}', Size: {size_mb:.2f}MB, Max allowed: {max_mb:.2f}MB"
        return f"{super().__str__()} Size: {size_mb:.2f}MB, Max allowed: {max_mb:.2f}MB"


def _estimate_object_size(value: Any, use_pickle: bool = False) -> int:
    """
    估算对象的序列化大小

    Args:
        value: 要估算的对象
        use_pickle: 是否使用 pickle（对于非 JSON 可序列化对象）

    Returns:
        估算的序列化大小（字节）
    """
    try:
        if use_pickle:
            # 使用 pickle 序列化（支持更多 Python 对象）
            return len(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
        else:
            # 默认使用 JSON（更安全，但只支持 JSON 可序列化对象）
            return len(json.dumps(value, default=str).encode("utf-8"))
    except (TypeError, ValueError, pickle.PicklingError) as e:
        # 如果 JSON 序列化失败，尝试 pickle
        if not use_pickle:
            try:
                return len(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
            except pickle.PicklingError:
                # 无法序列化，返回一个估计值
                logger.warning(f"Cannot estimate object size: {e}")
                return sys.getsizeof(value)
        logger.warning(f"Cannot estimate object size: {e}")
        return sys.getsizeof(value)


def _sanitize_error_message(error: str) -> str:
    """
    🔄 P0 FIX: Sanitize error messages to prevent internal path/key leakage.
    
    Removes:
    - /home/, /Users/, /var/, /tmp/ paths
    - redis:// URLs
    - sk-* API keys
    - file:// URLs
    - Internal IP addresses (127.0.0.1, 192.168.x.x, 10.x.x.x)
    """
    sanitized = str(error)
    
    # Remove file paths
    path_patterns = [
        r'/home/[^\s]+',
        r'/Users/[^\s]+',
        r'/var/[^\s]+',
        r'/tmp/[^\s]+',
        r'C:\\[^\s]+',
        r'D:\\[^\s]+',
    ]
    for pattern in path_patterns:
        sanitized = re.sub(pattern, '[PATH]', sanitized)
    
    # Remove Redis URLs
    sanitized = re.sub(r'redis://[^\s]+', '[REDIS_URL]', sanitized)
    sanitized = re.sub(r'rediss://[^\s]+', '[REDIS_URL]', sanitized)
    
    # Remove API keys (sk-*, api-key, token patterns)
    sanitized = re.sub(r'sk-[a-zA-Z0-9]+', '[API_KEY]', sanitized)
    sanitized = re.sub(r'api[_-]?key[_-]?[a-zA-Z0-9]+', '[API_KEY]', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'token[_-]?[a-zA-Z0-9]+', '[TOKEN]', sanitized, flags=re.IGNORECASE)
    
    # Remove file URLs
    sanitized = re.sub(r'file://[^\s]+', '[FILE_URL]', sanitized)
    
    # Remove internal IP addresses
    sanitized = re.sub(r'127\.0\.0\.1[^\s]*', '[LOCALHOST]', sanitized)
    sanitized = re.sub(r'192\.168\.[0-9]+\.[0-9]+', '[INTERNAL_IP]', sanitized)
    sanitized = re.sub(r'10\.[0-9]+\.[0-9]+\.[0-9]+', '[INTERNAL_IP]', sanitized)
    
    return sanitized

# ========== Backend ABC ==========


class BlackboardBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any: ...
    @abstractmethod
    async def put(self, key: str, value: Any, ttl: float | None = None) -> None: ...
    @abstractmethod
    async def wait_for_key(self, key: str, timeout: float | None = None) -> Any: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...
    @abstractmethod
    async def close(self) -> None: ...

    async def start(self) -> None:
        """Start the backend (optional for backends with background tasks)."""
        pass

    async def shutdown(self) -> None:
        """Shutdown the backend gracefully (optional)."""
        await self.close()

    @abstractmethod
    async def update(
        self, key: str, callback: Callable[[Any], Any], agent_id: str | None = None
    ) -> Any:
        """
        Atomically update a value using a callback.

        This performs a read-modify-write operation under lock protection.
        The callback receives the current value (or raises KeyError if missing)
        and returns the new value to store.

        Args:
            key: The key to update
            callback: Function that receives current value and returns new value
            agent_id: Optional agent ID for auditing (in secure backends)

        Returns:
            The new value after update

        Raises:
            KeyError: If the key does not exist
        """
        ...

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """
        🔄 Batch get multiple keys.
        Default implementation: iterate and call get() for each key.
        Override in subclasses for optimized batch retrieval.

        Args:
            keys: List of keys to retrieve

        Returns:
            Dict mapping keys to values (missing keys excluded)
        """
        result = {}
        for key in keys:
            try:
                result[key] = await self.get(key)
            except KeyError:
                pass  # Skip missing keys
        return result

    async def mset(self, items: dict[str, Any], ttl: float | None = None) -> None:
        """
        🔄 Batch set multiple keys.
        Default implementation: iterate and call put() for each key.
        Override in subclasses for optimized batch write.

        Args:
            items: Dict mapping keys to values
            ttl: Optional TTL for all keys (if supported)
        """
        for key, value in items.items():
            await self.put(key, value, ttl=ttl)


# ========== Memory Backend ==========


class MemoryBlackboard(BlackboardBackend):
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._condition = asyncio.Condition()

    async def get(self, key: str) -> Any:
        async with self._condition:
            if key not in self._data:
                raise KeyError(key)
            return self._data[key]

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """
        🔄 Optimized batch get for memory backend.
        Single lock acquisition, direct dict comprehension.
        """
        async with self._condition:
            return {k: self._data[k] for k in keys if k in self._data}

    async def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        async with self._condition:
            self._data[key] = value
            self._condition.notify_all()
    
    async def mset(self, items: dict[str, Any], ttl: float | None = None) -> None:
        """
        🔄 Optimized batch set for memory backend.
        Single lock acquisition, bulk dict update.
        """
        async with self._condition:
            self._data.update(items)
            self._condition.notify_all()

    async def wait_for_key(self, key: str, timeout: float | None = None) -> Any:
        deadline = time.monotonic() + timeout if timeout else None
        async with self._condition:
            while key not in self._data:
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise KeyError(f"Timeout waiting for key '{key}'")
                    try:
                        await asyncio.wait_for(self._condition.wait(), timeout=remaining)
                    except asyncio.TimeoutError:
                        raise KeyError(f"Timeout waiting for key '{key}'")
                else:
                    await self._condition.wait()
            return self._data[key]

    async def delete(self, key: str) -> None:
        async with self._condition:
            self._data.pop(key, None)
            self._condition.notify_all()

    async def close(self) -> None:
        pass

    async def update(
        self, key: str, callback: Callable[[Any], Any], agent_id: str | None = None
    ) -> Any:
        """
        Atomically update a value using a callback.

        Protected by the condition lock to ensure atomic read-modify-write.

        Args:
            key: The key to update
            callback: Function that receives current value and returns new value
            agent_id: Optional agent ID (unused in memory backend)

        Returns:
            The new value after update

        Raises:
            KeyError: If the key does not exist
        """
        async with self._condition:
            if key not in self._data:
                raise KeyError(key)
            current_value = self._data[key]
            new_value = callback(current_value)
            self._data[key] = new_value
            self._condition.notify_all()
            return new_value


# ========== TTL Memory Backend ==========


class TTLMemoryBlackboard(MemoryBlackboard):
    """
    Memory blackboard with TTL support and automatic cleanup.
    
    🔧 TTL Cleanup Enhancement:
    - Background cleanup task runs every cleanup_interval seconds
    - Proactively removes expired keys instead of passive cleanup on get()
    - Prevents memory leaks from long-idle expired keys
    
    Args:
        default_ttl: Default TTL for all keys (None = no expiry)
        cleanup_interval: Interval for background cleanup (default 60s)
    """
    
    def __init__(self, default_ttl: float | None = None, cleanup_interval: float = 60.0):
        super().__init__()
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._expires: dict[str, float] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._shutdown = False

    async def start(self) -> None:
        """
        🔄 Start the background cleanup task.
        
        This prevents memory leaks by proactively removing expired keys
        instead of waiting for get() to trigger cleanup.
        """
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(f"TTLMemoryBlackboard cleanup started (interval={self.cleanup_interval}s)")

    async def shutdown(self) -> None:
        """
        🔄 Gracefully shutdown the cleanup task.
        
        Cancels the background task and waits for it to complete.
        """
        self._shutdown = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("TTLMemoryBlackboard cleanup task stopped")
        await self.close()

    async def _cleanup_loop(self) -> None:
        """
        🔄 Background cleanup loop.
        
        Scans self._expires every cleanup_interval seconds and removes
        all expired keys. This prevents memory leaks from keys that
        are never accessed after their TTL expires.
        """
        while not self._shutdown:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if self._shutdown:
                    break
                
                now = time.monotonic()
                expired_keys = []
                
                # Find and remove all expired keys (within lock)
                async with self._condition:
                    for key, expiry in list(self._expires.items()):
                        if now > expiry:
                            expired_keys.append(key)
                            # Remove expired key
                            self._data.pop(key, None)
                            del self._expires[key]
                    
                    # Notify waiters if any keys were removed (within lock)
                    if expired_keys:
                        self._condition.notify_all()
                
                # Log cleanup statistics (outside lock)
                if expired_keys:
                    logger.debug(f"TTL cleanup: removed {len(expired_keys)} expired keys")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"TTL cleanup error: {e}")
                await asyncio.sleep(5.0)  # Backoff before retry

    async def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        async with self._condition:
            self._data[key] = value
            effective_ttl = ttl if ttl is not None else self.default_ttl
            if effective_ttl is not None:
                self._expires[key] = time.monotonic() + effective_ttl
            self._condition.notify_all()

    async def get(self, key: str) -> Any:
        async with self._condition:
            # Still check TTL on get for immediate expiry
            if key in self._expires and time.monotonic() > self._expires[key]:
                del self._data[key]
                del self._expires[key]
                raise KeyError(key)
            if key not in self._data:
                raise KeyError(key)
            return self._data[key]

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """
        🔄 Optimized batch get with TTL check.
        Single lock acquisition, filters expired keys.
        """
        async with self._condition:
            now = time.monotonic()
            result = {}
            for k in keys:
                if k in self._data:
                    # Check TTL
                    if k in self._expires and now > self._expires[k]:
                        del self._data[k]
                        del self._expires[k]
                    else:
                        result[k] = self._data[k]
            return result

    async def wait_for_key(self, key: str, timeout: float | None = None) -> Any:
        deadline = time.monotonic() + timeout if timeout else None
        async with self._condition:
            while True:
                if key in self._data:
                    if key in self._expires and time.monotonic() > self._expires[key]:
                        del self._data[key]
                        del self._expires[key]
                    else:
                        return self._data[key]
                if deadline is not None and time.monotonic() >= deadline:
                    raise KeyError(f"Timeout waiting for key '{key}'")
                remaining = None
                if deadline:
                    remaining = deadline - time.monotonic()
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    raise KeyError(f"Timeout waiting for key '{key}'")

    async def delete(self, key: str) -> None:
        async with self._condition:
            self._data.pop(key, None)
            self._expires.pop(key, None)
            self._condition.notify_all()

    async def update(
        self, key: str, callback: Callable[[Any], Any], agent_id: str | None = None
    ) -> Any:
        """
        Atomically update a value using a callback with TTL support.

        Protected by the condition lock to ensure atomic read-modify-write.
        Preserves TTL if the key has one, otherwise uses default_ttl.

        Args:
            key: The key to update
            callback: Function that receives current value and returns new value
            agent_id: Optional agent ID (unused in memory backend)

        Returns:
            The new value after update

        Raises:
            KeyError: If the key does not exist or has expired
        """
        async with self._condition:
            # Check TTL
            if key in self._expires and time.monotonic() > self._expires[key]:
                del self._data[key]
                del self._expires[key]
                raise KeyError(key)

            if key not in self._data:
                raise KeyError(key)

            current_value = self._data[key]
            new_value = callback(current_value)
            self._data[key] = new_value

            # Preserve or update TTL
            if key in self._expires:
                # Keep existing expiry
                pass
            elif self.default_ttl is not None:
                # Apply default TTL if key didn't have one
                self._expires[key] = time.monotonic() + self.default_ttl

            self._condition.notify_all()
            return new_value

    def get_stats(self) -> dict:
        """Get TTL statistics."""
        now = time.monotonic()
        total_keys = len(self._data)
        ttl_keys = len(self._expires)
        expired_pending = sum(1 for expiry in self._expires.values() if now > expiry)
        return {
            "total_keys": total_keys,
            "ttl_keys": ttl_keys,
            "expired_pending": expired_pending,
            "cleanup_interval": self.cleanup_interval,
            "cleanup_running": self._cleanup_task is not None and not self._cleanup_task.done(),
        }


# ========== Redis Backend ==========

try:
    import redis.asyncio as aioredis
    from redis.asyncio import ConnectionPool

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    ConnectionPool = None  # type: ignore


class RedisBlackboard(BlackboardBackend):
    """
    Redis-backed blackboard with connection pool management.
    
    🔧 Connection Pool Enhancement:
    - Uses explicit ConnectionPool for better resource control
    - Shared pool across all operations
    - TTL handled by Redis SETEX command
    
    Args:
        redis_url: Redis connection URL
        prefix: Key prefix for all blackboard keys
        db: Redis database number
        max_connections: Maximum connections in pool (default 10)
        socket_timeout: Socket timeout in seconds
        poll_interval: Interval for wait_for_key polling
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost",
        prefix: str = "blackboard",
        db: int = 0,
        max_connections: int = 10,
        socket_timeout: float = 5.0,
        poll_interval: float = 0.05,
    ):
        if not _REDIS_AVAILABLE:
            raise ImportError("redis required")
        
        # 🔄 Use explicit ConnectionPool
        self._pool: ConnectionPool = aioredis.ConnectionPool.from_url(
            redis_url,
            db=db,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            decode_responses=False,
        )
        self.redis = aioredis.Redis(connection_pool=self._pool)
        self.prefix = prefix
        self.db = db
        self._poll_interval = poll_interval
        self.max_connections = max_connections

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any:
        data = await self.redis.get(self._key(key))
        if data is None:
            raise KeyError(key)
        data_str = data if isinstance(data, str) else data.decode()
        return json.loads(data_str)

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """
        🔄 Optimized batch get for Redis using MGET command.
        Single network round-trip for multiple keys.
        """
        if not keys:
            return {}
        
        redis_keys = [self._key(k) for k in keys]
        results = await self.redis.mget(redis_keys)
        
        result = {}
        for i, (key, data) in enumerate(zip(keys, results)):
            if data is not None:
                try:
                    data_str = data if isinstance(data, str) else data.decode()
                    result[key] = json.loads(data_str)
                except json.JSONDecodeError:
                    result[key] = data
        return result

    async def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        k = self._key(key)
        data = json.dumps(value, default=str)
        if ttl is not None:
            await self.redis.setex(k, max(1, math.ceil(ttl)), data)
        else:
            await self.redis.set(k, data)
    
    async def mset(self, items: dict[str, Any], ttl: float | None = None) -> None:
        """
        🔄 Optimized batch set for Redis backend.
        Uses Redis MSET for bulk write (single network round-trip).
        Note: MSET doesn't support TTL, so TTL keys use SETEX in pipeline.
        
        Args:
            items: Dict mapping keys to values
            ttl: Optional TTL for all keys (uses pipeline if set)
        """
        if not items:
            return
        
        if ttl is not None:
            # Use pipeline for TTL-enabled writes
            redis_keys = [self._key(k) for k in items.keys()]
            async with self.redis.pipeline() as pipe:
                for rkey, value in zip(redis_keys, items.values()):
                    data = json.dumps(value, default=str)
                    pipe.setex(rkey, max(1, math.ceil(ttl)), data)
                await pipe.execute()
        else:
            # Use MSET for bulk write (no TTL)
            mapping = {}
            for key, value in items.items():
                rkey = self._key(key)
                mapping[rkey] = json.dumps(value, default=str)
            await self.redis.mset(mapping)

    async def wait_for_key(self, key: str, timeout: float | None = None) -> Any:
        deadline = time.monotonic() + timeout if timeout else None
        while True:
            try:
                return await self.get(key)
            except KeyError:
                if deadline and time.monotonic() >= deadline:
                    raise KeyError(f"Timeout waiting for key '{key}'")
                await asyncio.sleep(self._poll_interval)

    async def delete(self, key: str) -> None:
        await self.redis.delete(self._key(key))

    async def update(
        self, key: str, callback: Callable[[Any], Any], agent_id: str | None = None
    ) -> Any:
        """
        Atomically update a value using a callback.

        Note: Redis doesn't have built-in atomic read-modify-write for arbitrary
        callbacks. This implementation uses a distributed lock pattern with WATCH.

        Args:
            key: The key to update
            callback: Function that receives current value and returns new value
            agent_id: Optional agent ID (unused in Redis backend)

        Returns:
            The new value after update

        Raises:
            KeyError: If the key does not exist
        """
        redis_key = self._key(key)

        # Use WATCH for optimistic locking
        while True:
            try:
                async with self.redis.pipeline() as pipe:
                    # Watch the key for changes
                    await pipe.watch(redis_key)

                    # Get current value
                    data = await self.redis.get(redis_key)
                    if data is None:
                        await pipe.unwatch()
                        raise KeyError(key)

                    data_str = data if isinstance(data, str) else data.decode()
                    current_value = json.loads(data_str)

                    # Apply callback
                    new_value = callback(current_value)
                    new_data = json.dumps(new_value, default=str)

                    # Check TTL
                    ttl_data = await self.redis.ttl(redis_key)

                    # Transactional set
                    pipe.multi()
                    if ttl_data > 0:
                        # Preserve TTL
                        pipe.setex(redis_key, ttl_data, new_data)
                    else:
                        pipe.set(redis_key, new_data)

                    await pipe.execute()
                    return new_value

            except aioredis.WatchError:
                # Key was modified by another client, retry
                continue

    async def close(self) -> None:
        await self.redis.aclose()
        await self._pool.disconnect()

    def get_connection_stats(self) -> dict:
        """Get connection pool statistics."""
        return {
            "max_connections": self.max_connections,
            "prefix": self.prefix,
            "db": self.db,
        }


# ========== Secure Blackboard ==========


class SecureBlackboard:
    def __init__(self, backend: BlackboardBackend, max_audit: int = 1000, max_object_size: int = 10 * 1024 * 1024):
        """
        Args:
            backend: 黑板后端实现
            max_audit: 最大审计日志条数
            max_object_size: 最大对象大小限制（字节），默认 10MB
        """
        self._backend = backend
        self._permissions: dict[str, Capability] = {}
        self._perm_lock = asyncio.Lock()
        self._audit_log: list[dict] = []
        self._max_audit = max_audit
        self._audit_lock = asyncio.Lock()
        self._max_object_size = max_object_size

    async def start(self) -> None:
        """Start the backend."""
        await self._backend.start()

    async def shutdown(self) -> None:
        """Shutdown the backend gracefully."""
        await self._backend.shutdown()

    async def register_agent(self, agent_id: str, cap: Capability):
        async with self._perm_lock:
            self._permissions[agent_id] = cap

    async def unregister_agent(self, agent_id: str):
        async with self._perm_lock:
            self._permissions.pop(agent_id, None)

    def view_for(self, agent_id: str) -> "AuditedBlackboardView":
        return AuditedBlackboardView(self, agent_id)

    async def sys_put(self, key: str, value: Any, ttl: float | None = None):
        """
        系统级写入（绕过权限检查）

        Args:
            key: 键名
            value: 值
            ttl: TTL（可选）

        Raises:
            ValueError: 如果值不可 JSON 序列化
            ObjectTooLargeError: 如果对象超过大小限制
        """
        # 🔧 大对象检测：检查对象大小
        object_size = _estimate_object_size(value)
        if object_size > self._max_object_size:
            raise ObjectTooLargeError(
                f"Object exceeds maximum size limit",
                object_size=object_size,
                max_size=self._max_object_size,
                key=key,
            )

        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            # 🔄 P0 FIX: Sanitize error message to prevent leakage
            sanitized_error = _sanitize_error_message(str(e))
            raise ValueError(f"Value for key '{key}' is not JSON-serializable: {sanitized_error}")
        await self._backend.put(key, value, ttl)

    async def sys_get(self, key: str) -> Any:
        return await self._backend.get(key)

    async def sys_mget(self, keys: list[str]) -> dict[str, Any]:
        """System-level batch get (bypasses permission check)."""
        return await self._backend.mget(keys)
    
    async def sys_mset(self, items: dict[str, Any], ttl: float | None = None) -> None:
        """
        System-level batch set (bypasses permission check).

        Raises:
            ValueError: If any value is not JSON-serializable
            ObjectTooLargeError: If any object exceeds size limit
        """
        # Validate all values are JSON-serializable and within size limit
        for key, value in items.items():
            # 🔧 大对象检测：检查每个对象大小
            object_size = _estimate_object_size(value)
            if object_size > self._max_object_size:
                raise ObjectTooLargeError(
                    f"Object exceeds maximum size limit",
                    object_size=object_size,
                    max_size=self._max_object_size,
                    key=key,
                )
            try:
                json.dumps(value)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Value for key '{key}' is not JSON-serializable: {e}")
        await self._backend.mset(items, ttl)

    async def sys_wait_for_key(self, key: str, timeout: float | None = None) -> Any:
        return await self._backend.wait_for_key(key, timeout)

    async def sys_delete(self, key: str) -> None:
        await self._backend.delete(key)

    def _check_permission(self, cap: Capability, key: str, read: bool) -> bool:
        """检查权限，支持 fnmatch 模式匹配；禁止裸 * 通配符"""
        keys = cap.read_keys if read else cap.write_keys
        for p in keys:
            if p == "*":
                raise PermissionError("Wildcard '*' is not allowed. Use 'prefix:*' pattern instead.")
            if fnmatch(key, p):
                return True
        return False

    async def mget_and_audit(self, agent_id: str, keys: list[str]) -> dict[str, Any]:
        """
        🔄 Batch get with permission check and audit.
        Single permission check for all keys.
        """
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        
        # Filter keys by permission
        allowed_keys = [k for k in keys if self._check_permission(cap, k, read=True)]
        
        # Batch retrieve
        result = await self._backend.mget(allowed_keys)
        
        # Single audit entry for batch operation
        await self._add_audit("mget", agent_id, f"{len(result)} keys")
        return result

    async def wait_and_audit(self, agent_id: str, key: str, timeout: float | None = None) -> Any:
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not self._check_permission(cap, key, read=True):
            raise PermissionError(f"Agent {agent_id} lacks read permission for {key}")

        val = await self._backend.wait_for_key(key, timeout)

        # 等待后再次验证 Agent 仍注册且有权限 (TOCTOU 修复)
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
            if cap is None or not self._check_permission(cap, key, read=True):
                raise PermissionError(f"Agent '{agent_id}' lost permission during wait for key '{key}'")
        await self._add_audit("wait", agent_id, key)
        return val

    async def get_and_audit(self, agent_id: str, key: str) -> Any:
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not self._check_permission(cap, key, read=True):
            raise PermissionError(f"Agent {agent_id} lacks read permission for {key}")
        val = await self._backend.get(key)
        await self._add_audit("get", agent_id, key)
        return val

    async def put_and_audit(self, agent_id: str, key: str, value: Any, ttl: float | None = None) -> None:
        """
        写入并审计（带权限检查）

        Args:
            agent_id: Agent ID
            key: 键名
            value: 值
            ttl: TTL（可选）

        Raises:
            PermissionError: 如果 Agent 未注册或缺少写权限
            ValueError: 如果值不可 JSON 序列化
            ObjectTooLargeError: 如果对象超过大小限制
        """
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not self._check_permission(cap, key, read=False):
            raise PermissionError(f"Agent {agent_id} lacks write permission for {key}")

        # 🔧 大对象检测：检查对象大小
        object_size = _estimate_object_size(value)
        if object_size > self._max_object_size:
            raise ObjectTooLargeError(
                f"Object exceeds maximum size limit",
                object_size=object_size,
                max_size=self._max_object_size,
                key=key,
            )

        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Value for key '{key}' is not JSON-serializable: {e}")
        await self._backend.put(key, value, ttl)
        await self._add_audit("put", agent_id, key)

    async def update_and_audit(
        self, agent_id: str, key: str, callback: Callable[[Any], Any]
    ) -> Any:
        """
        Atomically update a value with permission check and audit.

        Args:
            agent_id: Agent performing the update
            key: Key to update
            callback: Function to apply to current value

        Returns:
            New value after update

        Raises:
            PermissionError: If agent lacks read/write permission
            KeyError: If key does not exist
        """
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not self._check_permission(cap, key, read=True):
            raise PermissionError(f"Agent {agent_id} lacks read permission for {key}")
        if not self._check_permission(cap, key, read=False):
            raise PermissionError(f"Agent {agent_id} lacks write permission for {key}")

        new_value = await self._backend.update(key, callback, agent_id)
        await self._add_audit("update", agent_id, key)
        return new_value

    async def _add_audit(self, action: str, agent_id: str, key: str):
        async with self._audit_lock:
            self._audit_log.append({"action": action, "agent": agent_id, "key": key, "timestamp": time.time()})
            if len(self._audit_log) > self._max_audit:
                self._audit_log = self._audit_log[-self._max_audit :]

    async def close(self) -> None:
        await self._backend.close()


class AuditedBlackboardView:
    def __init__(self, secure: SecureBlackboard, agent_id: str):
        self._secure = secure
        self.agent_id = agent_id

    async def get(self, key: str) -> Any:
        return await self._secure.get_and_audit(self.agent_id, key)

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """🔄 Batch get multiple keys."""
        return await self._secure.mget_and_audit(self.agent_id, keys)

    async def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        await self._secure.put_and_audit(self.agent_id, key, value, ttl)

    async def update(self, key: str, callback: Callable[[Any], Any]) -> Any:
        """Atomically update a value."""
        return await self._secure.update_and_audit(self.agent_id, key, callback)

    async def wait_for_key(self, key: str, timeout: float | None = None) -> Any:
        return await self._secure.wait_and_audit(self.agent_id, key, timeout)


class OrchestratorReadonlyView:
    """编排器内部任务专用的只读黑板视图，防止绕过 Agent 权限写入，并记录审计日志"""

    def __init__(self, secure: SecureBlackboard):
        self._secure = secure

    async def get(self, key: str) -> Any:
        value = await self._secure.sys_get(key)
        await self._secure._add_audit("sys_get", "__orchestrator__", key)
        return value

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """🔄 Batch get multiple keys (system level)."""
        result = await self._secure.sys_mget(keys)
        await self._secure._add_audit("sys_mget", "__orchestrator__", f"{len(result)} keys")
        return result

    async def wait_for_key(self, key: str, timeout: float | None = None) -> Any:
        value = await self._secure.sys_wait_for_key(key, timeout)
        await self._secure._add_audit("sys_wait", "__orchestrator__", key)
        return value


# ========== Encryption ==========


class KeyProvider(ABC):
    @abstractmethod
    def get_key(self, version: str | None = None) -> bytes: ...


class EnvKeyProvider(KeyProvider):
    def __init__(self, env_var="HIVEFLOW_ENCRYPTION_KEY"):
        self.env_var = env_var

    def get_key(self, version=None):
        key = os.environ.get(self.env_var)
        if not key:
            raise RuntimeError(f"Environment variable {self.env_var} not set")
        return key.encode()


class FileKeyProvider(KeyProvider):
    def __init__(self, file_path: str):
        self._file_path = file_path

    def get_key(self, version=None):
        if not os.path.exists(self._file_path):
            raise RuntimeError(f"Key file not found: {self._file_path}")
        with open(self._file_path, "rb") as f:
            return f.read().strip()


try:
    from cryptography.fernet import Fernet

    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False


class EncryptedBlackboard(BlackboardBackend):
    def __init__(
        self,
        base_backend: BlackboardBackend,
        key_provider: KeyProvider,
        key_version: str | None = None,
        use_compression: bool = False,
    ):
        if not _FERNET_AVAILABLE:
            raise ImportError("cryptography library is required")
        self._backend = base_backend
        self._fernet = Fernet(key_provider.get_key(key_version))
        self._use_compression = use_compression

    async def start(self) -> None:
        await self._backend.start()

    async def shutdown(self) -> None:
        await self._backend.shutdown()

    def _encrypt(self, value: Any) -> str:
        raw = json.dumps(value, default=str).encode("utf-8")
        if self._use_compression:
            raw = zlib.compress(raw)
        encrypted_bytes = self._fernet.encrypt(raw)
        return base64.b64encode(encrypted_bytes).decode("ascii")

    def _decrypt(self, encrypted_str: str) -> Any:
        encrypted_bytes = base64.b64decode(encrypted_str.encode("ascii"))
        raw = self._fernet.decrypt(encrypted_bytes)
        if self._use_compression:
            raw = zlib.decompress(raw)
        return json.loads(raw.decode("utf-8"))

    async def get(self, key: str) -> Any:
        return self._decrypt(await self._backend.get(key))

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """
        🔄 Batch get with decryption.
        """
        encrypted_result = await self._backend.mget(keys)
        return {k: self._decrypt(v) for k, v in encrypted_result.items()}

    async def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        await self._backend.put(key, self._encrypt(value), ttl)

    async def wait_for_key(self, key: str, timeout: float | None = None) -> Any:
        return self._decrypt(await self._backend.wait_for_key(key, timeout))

    async def delete(self, key: str) -> None:
        await self._backend.delete(key)

    async def update(
        self, key: str, callback: Callable[[Any], Any], agent_id: str | None = None
    ) -> Any:
        """
        Atomically update a value using a callback with encryption.

        Delegates to underlying backend's update, but encrypts/decrypts values.

        Args:
            key: The key to update
            callback: Function that receives decrypted value and returns new value
            agent_id: Optional agent ID (passed to underlying backend)

        Returns:
            The new value after update (decrypted)

        Raises:
            KeyError: If the key does not exist
        """
        # Create wrapper callback that decrypts, applies callback, then encrypts
        def encrypted_callback(encrypted_value: Any) -> Any:
            decrypted_value = self._decrypt(encrypted_value)
            new_value = callback(decrypted_value)
            return self._encrypt(new_value)

        # Delegate to underlying backend
        encrypted_new_value = await self._backend.update(key, encrypted_callback, agent_id)
        return self._decrypt(encrypted_new_value)

    async def close(self) -> None:
        await self._backend.close()