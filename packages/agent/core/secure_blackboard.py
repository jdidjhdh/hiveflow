import fnmatch
import asyncio
import time
import json
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Set


@dataclass
class Capability:
    agent_id: str
    skills: Set[str]
    read_keys: Set[str]
    write_keys: Set[str]
    load: float = 0.0
    state: str = "starting"
    weight: float = 1.0
    pending_tasks: int = 0
    max_queue_size: int = 0


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
            while True:
                if key in self._data:
                    return self._data[key]
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

    async def delete(self, key: str) -> None:
        async with self._condition:
            self._data.pop(key, None)
            self._condition.notify_all()

    async def close(self) -> None:
        pass


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
        await self._backend.put(key, value, ttl)

    async def sys_get(self, key: str) -> Any:
        return await self._backend.get(key)

    async def sys_wait_for_key(self, key: str, timeout: Optional[float] = None) -> Any:
        return await self._backend.wait_for_key(key, timeout)

    async def sys_delete(self, key: str) -> None:
        await self._backend.delete(key)

    async def _check_permission(self, cap: Capability, key: str, read: bool) -> bool:
        """检查权限，禁止裸 * 通配符，只允许 prefix:* 形式"""
        keys = cap.read_keys if read else cap.write_keys
        for p in keys:
            if p == "*":
                raise PermissionError("Wildcard '*' is not allowed. Use 'prefix:*' pattern instead.")
            if fnmatch.fnmatch(key, p):
                return True
        return False

    async def get_and_audit(self, agent_id: str, key: str) -> Any:
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not await self._check_permission(cap, key, read=True):
            raise PermissionError(f"Agent {agent_id} lacks read permission for {key}")
        val = await self._backend.get(key)
        await self._add_audit("get", agent_id, key)
        return val

    async def put_and_audit(self, agent_id: str, key: str, value: Any, ttl: Optional[float] = None) -> None:
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not await self._check_permission(cap, key, read=False):
            raise PermissionError(f"Agent {agent_id} lacks write permission for {key}")
        try:
            json.dumps(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Value for key '{key}' is not JSON serializable: {e}")
        await self._backend.put(key, value, ttl)
        await self._add_audit("put", agent_id, key)

    async def wait_and_audit(self, agent_id: str, key: str, timeout: Optional[float] = None) -> Any:
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
        if cap is None:
            raise PermissionError(f"Agent '{agent_id}' not registered")
        if not await self._check_permission(cap, key, read=True):
            raise PermissionError(f"Agent {agent_id} lacks read permission for {key}")
        val = await self._backend.wait_for_key(key, timeout)
        async with self._perm_lock:
            cap = self._permissions.get(agent_id)
            if cap is None or not await self._check_permission(cap, key, read=True):
                raise PermissionError(f"Agent '{agent_id}' lost permission during wait")
        await self._add_audit("wait", agent_id, key)
        return val

    async def record_audit(self, action: str, agent_id: str, key: str):
        """公开审计记录方法，供 OrchestratorReadonlyView 等使用"""
        await self._add_audit(action, agent_id, key)

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
