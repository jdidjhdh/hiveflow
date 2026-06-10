import math
from abc import ABC, abstractmethod
import asyncio
import json
import time
import os
import base64
import zlib
import logging
from typing import Any, Optional, Dict, List

try:
    from . import Capability
except ImportError:
    from hiveflow import Capability

logger = logging.getLogger(__name__)

# ========== Backend ABC ==========

class BlackboardBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any: ...
    @abstractmethod
    async def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None: ...
    @abstractmethod
    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...
    @abstractmethod
    async def close(self) -> None: ...

# ========== Memory Backend ==========

class MemoryBlackboard(BlackboardBackend):
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._condition = asyncio.Condition()

    async def get(self, key: str) -> Any:
        async with self._condition:
            if key not in self._data:
                raise KeyError(key)
            return self._data[key]

    async def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        async with self._condition:
            self._data[key] = value
            self._condition.notify_all()

    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
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

# ========== TTL Memory Backend ==========

class TTLMemoryBlackboard(MemoryBlackboard):
    def __init__(self, default_ttl: Optional[float] = None):
        super().__init__()
        self.default_ttl = default_ttl
        self._expires: Dict[str, float] = {}

    async def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        async with self._condition:
            self._data[key] = value
            effective_ttl = ttl if ttl is not None else self.default_ttl
            if effective_ttl is not None:
                self._expires[key] = time.monotonic() + effective_ttl
            self._condition.notify_all()

    async def get(self, key: str) -> Any:
        async with self._condition:
            if key in self._expires and time.monotonic() > self._expires[key]:
                del self._data[key]
                del self._expires[key]
                raise KeyError(key)
            if key not in self._data:
                raise KeyError(key)
            return self._data[key]

    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
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

# ========== Redis Backend ==========

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RedisBlackboard(BlackboardBackend):
    def __init__(self, redis_url="redis://localhost", prefix="blackboard", db=0,
                 max_connections=10, socket_timeout=5.0, poll_interval=0.05):
        if not _REDIS_AVAILABLE:
            raise ImportError("redis required")
        self.redis = aioredis.from_url(redis_url, db=db,
                                       max_connections=max_connections,
                                       socket_timeout=socket_timeout)
        self.prefix = prefix
        self.db = db
        self._poll_interval = poll_interval

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any:
        data = await self.redis.get(self._key(key))
        if data is None:
            raise KeyError(key)
        return json.loads(data)

    async def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        k = self._key(key)
        data = json.dumps(value, default=str)
        if ttl is not None:
            await self.redis.setex(k, max(1, math.ceil(ttl)), data)
        else:
            await self.redis.set(k, data)

    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
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

    async def close(self) -> None:
        await self.redis.close()

# ========== Secure Blackboard ==========

from fnmatch import fnmatch

class SecureBlackboard:
    def __init__(self, backend: BlackboardBackend, max_audit: int = 1000):
        self._backend = backend
        self._permissions: Dict[str, Capability] = {}
        self._perm_lock = asyncio.Lock()
        self._audit_log: List[dict] = []
        self._max_audit = max_audit
        self._audit_lock = asyncio.Lock()

    async def register_agent(self, agent_id: str, cap: Capability):
        async with self._perm_lock:
            self._permissions[agent_id] = cap

    async def unregister_agent(self, agent_id: str):
        async with self._perm_lock:
            self._permissions.pop(agent_id, None)

    def view_for(self, agent_id: str) -> 'AuditedBlackboardView':
        return AuditedBlackboardView(self, agent_id)

    async def sys_put(self, key: str, value: Any, ttl: Optional[float] = None):
        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Value for key '{key}' is not JSON-serializable: {e}")
        await self._backend.put(key, value, ttl)

    async def sys_get(self, key: str) -> Any:
        return await self._backend.get(key)

    async def sys_wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
        return await self._backend.wait_for_key(key, timeout)

    async def sys_delete(self, key: str) -> None:
        await self._backend.delete(key)

    def _check_permission(self, cap: Capability, key: str, read: bool) -> bool:
        """检查权限，支持 fnmatch 模式匹配"""
        keys = cap.read_keys if read else cap.write_keys
        for p in keys:
            if fnmatch(key, p):
                return True
        return False

    async def wait_and_audit(self, agent_id: str, key: str, timeout: Optional[float] = None) -> Any:
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

    async def put_and_audit(self, agent_id: str, key: str, value: Any, ttl: Optional[float] = None) -> None:
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not self._check_permission(cap, key, read=False):
            raise PermissionError(f"Agent {agent_id} lacks write permission for {key}")
        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Value for key '{key}' is not JSON-serializable: {e}")
        await self._backend.put(key, value, ttl)
        await self._add_audit("put", agent_id, key)

    async def _add_audit(self, action: str, agent_id: str, key: str):
        async with self._audit_lock:
            self._audit_log.append({
                "action": action, "agent": agent_id, "key": key, "timestamp": time.time()
            })
            if len(self._audit_log) > self._max_audit:
                self._audit_log = self._audit_log[-self._max_audit:]

    async def close(self) -> None:
        await self._backend.close()


class AuditedBlackboardView:
    def __init__(self, secure: SecureBlackboard, agent_id: str):
        self._secure = secure
        self.agent_id = agent_id

    async def get(self, key: str) -> Any:
        return await self._secure.get_and_audit(self.agent_id, key)

    async def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        await self._secure.put_and_audit(self.agent_id, key, value, ttl)

    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
        return await self._secure.wait_and_audit(self.agent_id, key, timeout)


class OrchestratorReadonlyView:
    """编排器内部任务专用的只读黑板视图，防止绕过 Agent 权限写入，并记录审计日志"""
    def __init__(self, secure: SecureBlackboard):
        self._secure = secure

    async def get(self, key: str) -> Any:
        value = await self._secure.sys_get(key)
        await self._secure._add_audit("sys_get", "__orchestrator__", key)
        return value

    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
        value = await self._secure.sys_wait_for_key(key, timeout)
        await self._secure._add_audit("sys_wait", "__orchestrator__", key)
        return value

# ========== Encryption ==========

class KeyProvider(ABC):
    @abstractmethod
    def get_key(self, version: Optional[str] = None) -> bytes: ...

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
        with open(self._file_path, 'rb') as f:
            return f.read().strip()

try:
    from cryptography.fernet import Fernet
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False

class EncryptedBlackboard(BlackboardBackend):
    def __init__(self, base_backend: BlackboardBackend, key_provider: KeyProvider,
                 key_version: Optional[str] = None, use_compression: bool = False):
        if not _FERNET_AVAILABLE:
            raise ImportError("cryptography library is required")
        self._backend = base_backend
        self._fernet = Fernet(key_provider.get_key(key_version))
        self._use_compression = use_compression

    def _encrypt(self, value: Any) -> str:
        raw = json.dumps(value, default=str).encode('utf-8')
        if self._use_compression:
            raw = zlib.compress(raw)
        encrypted_bytes = self._fernet.encrypt(raw)
        return base64.b64encode(encrypted_bytes).decode('ascii')

    def _decrypt(self, encrypted_str: str) -> Any:
        encrypted_bytes = base64.b64decode(encrypted_str.encode('ascii'))
        raw = self._fernet.decrypt(encrypted_bytes)
        if self._use_compression:
            raw = zlib.decompress(raw)
        return json.loads(raw.decode('utf-8'))

    async def get(self, key: str) -> Any:
        return self._decrypt(await self._backend.get(key))

    async def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        await self._backend.put(key, self._encrypt(value), ttl)

    async def wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
        return self._decrypt(await self._backend.wait_for_key(key, timeout))

    async def delete(self, key: str) -> None:
        await self._backend.delete(key)

    async def close(self) -> None:
        await self._backend.close()