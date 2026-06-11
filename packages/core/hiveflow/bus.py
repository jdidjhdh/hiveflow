import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Callable

try:
    from . import ECM, Expectation
except ImportError:
    from hiveflow import ECM, Expectation

logger = logging.getLogger(__name__)


class EventBus(ABC):
    @abstractmethod
    async def publish(self, topic: str, msg: ECM) -> None: ...

    @abstractmethod
    async def subscribe(
        self, topic: str, handler: Callable[[ECM], Awaitable[None]], tags: set[str] | None = None
    ) -> str: ...

    @abstractmethod
    async def unsubscribe(self, topic: str, subscriber_id: str) -> None: ...

    @abstractmethod
    async def update_subscription_tags(self, topic: str, subscriber_id: str, tags: set[str]) -> None: ...

    @abstractmethod
    async def register_intent(self, intent_id: str, timeout: float) -> None: ...

    @abstractmethod
    async def complete_intent(self, intent_id: str, success: bool = True) -> None: ...

    @abstractmethod
    async def is_intent_active(self, intent_id: str) -> bool: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


class InProcessEventBus(EventBus):
    def __init__(self):
        self._topics: dict[str, dict[str, tuple[Callable[[ECM], Awaitable[None]], set[str]]]] = defaultdict(dict)
        self._intents: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._sub_counter = 0

    def _next_sub_id_locked(self) -> str:
        self._sub_counter += 1
        return f"sub_{self._sub_counter}"

    async def publish(self, topic: str, msg: ECM) -> None:
        async with self._lock:
            subs = dict(self._topics.get(topic, {}))
        for handler, tags in subs.values():
            if tags and msg.required_skills and not tags.intersection(set(msg.required_skills)):
                continue
            try:
                await handler(msg)
            except Exception:
                logger.exception(f"Handler error on topic {topic}")

    async def subscribe(
        self, topic: str, handler: Callable[[ECM], Awaitable[None]], tags: set[str] | None = None
    ) -> str:
        tags = tags or set()
        async with self._lock:
            sub_id = self._next_sub_id_locked()
            self._topics[topic][sub_id] = (handler, tags)
        return sub_id

    async def unsubscribe(self, topic: str, subscriber_id: str) -> None:
        async with self._lock:
            self._topics[topic].pop(subscriber_id, None)

    async def update_subscription_tags(self, topic: str, subscriber_id: str, tags: set[str]) -> None:
        async with self._lock:
            if subscriber_id in self._topics.get(topic, {}):
                handler, _ = self._topics[topic][subscriber_id]
                self._topics[topic][subscriber_id] = (handler, tags)

    async def register_intent(self, intent_id: str, timeout: float) -> None:
        async with self._lock:
            if intent_id in self._intents:
                return
            task = asyncio.create_task(self._intent_timeout(intent_id, timeout))
            self._intents[intent_id] = task

    async def complete_intent(self, intent_id: str, success: bool = True) -> None:
        async with self._lock:
            task = self._intents.pop(intent_id, None)
        if task and not task.done():
            task.cancel()

    async def is_intent_active(self, intent_id: str) -> bool:
        async with self._lock:
            return intent_id in self._intents

    async def _intent_timeout(self, intent_id: str, timeout: float) -> None:
        try:
            await asyncio.sleep(timeout)
        except asyncio.CancelledError:
            return
        # 仅在意图仍存在时才发布超时，防止已完成的意图产生虚假事件
        async with self._lock:
            task = self._intents.pop(intent_id, None)
        if task is not None:
            await self.publish(
                "intent.timeout", ECM(trace_id=intent_id, intent="intent.timeout", intent_id=intent_id, emitter="bus")
            )

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        async with self._lock:
            tasks = list(self._intents.values())
            self._intents.clear()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# ========== Redis Event Bus ==========

try:
    import redis.asyncio as aioredis

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RedisEventBus(EventBus):
    def __init__(self, redis_url="redis://localhost", prefix="hiveflow", db=0, max_connections=10, socket_timeout=5.0):
        if not _REDIS_AVAILABLE:
            raise ImportError("redis required")
        self.redis = aioredis.from_url(redis_url, db=db, max_connections=max_connections, socket_timeout=socket_timeout)
        self.prefix = prefix
        self.db = db
        self._lock = asyncio.Lock()
        self._sub_counter = 0
        self._listener_tasks: dict[str, asyncio.Task] = {}
        self._subscriptions: dict[str, tuple[str, Callable, set[str]]] = {}
        self._local_intents: dict[str, asyncio.Task] = {}
        self._intent_monitor_task: asyncio.Task | None = None
        self._use_local_intent_timeout: bool | None = None
        self._shutdown = False
        self._intent_mode_lock = asyncio.Lock()

    async def _ensure_keyspace_notification(self) -> bool:
        try:
            config = await self.redis.config_get("notify-keyspace-events")
            val = config.get("notify-keyspace-events", "")
            if "E" in val and "x" in val:
                return True
        except Exception:
            pass
        logger.critical("Redis keyspace notifications not enabled (need 'Ex'). Falling back to local intent timeout.")
        return False

    async def _init_intent_mode(self):
        if self._use_local_intent_timeout is not None:
            return
        async with self._intent_mode_lock:
            if self._use_local_intent_timeout is not None:
                return
            use_redis = await self._ensure_keyspace_notification()
            self._use_local_intent_timeout = not use_redis
            if use_redis:
                logger.info("Intent timeout mode: Redis keyspace notifications + local safeguard.")
                self._intent_monitor_task = asyncio.create_task(self._monitor_intent_expiry())
            else:
                logger.info("Intent timeout mode: local timers only.")

    async def start(self) -> None:
        await self._init_intent_mode()

    async def publish(self, topic: str, msg: ECM) -> None:
        key = f"{self.prefix}:topic:{topic}"
        data = json.dumps(
            {
                "trace_id": msg.trace_id,
                "intent": msg.intent,
                "intent_id": msg.intent_id,
                "emitter": msg.emitter,
                "expectation": msg.expectation.__dict__ if msg.expectation else None,
                "payload": msg.payload,
                "reply_to": msg.reply_to,
                "timestamp": msg.timestamp,
                "required_skills": msg.required_skills,
                "priority": msg.priority,
                "metadata": msg.metadata,
            },
            default=str,
        )
        await self.redis.publish(key, data)

    async def subscribe(self, topic: str, handler, tags=None) -> str:
        tags = tags or set()
        async with self._lock:
            sub_id = f"sub_{self._sub_counter}"
            self._sub_counter += 1
            self._subscriptions[sub_id] = (topic, handler, tags)

        key = f"{self.prefix}:topic:{topic}"

        # 带有自动重连的监听器（指数退避，尊重关闭信号）
        async def listener():
            backoff = 0.1
            while not self._shutdown:
                try:
                    async with self.redis.pubsub() as pubsub:
                        await pubsub.subscribe(key)
                        backoff = 0.1  # 重置退避
                        async for message in pubsub.listen():
                            if self._shutdown:
                                break
                            if message["type"] != "message":
                                continue
                            async with self._lock:
                                sub_info = self._subscriptions.get(sub_id)
                                if sub_info is None:
                                    break
                                _, current_handler, current_tags = sub_info
                            data = json.loads(message["data"])
                            exp = data.get("expectation")
                            expectation = Expectation(**exp) if isinstance(exp, dict) else None
                            msg = ECM(
                                trace_id=data["trace_id"],
                                intent=data["intent"],
                                intent_id=data["intent_id"],
                                emitter=data["emitter"],
                                expectation=expectation,
                                payload=data.get("payload", {}),
                                reply_to=data.get("reply_to", ""),
                                timestamp=data.get("timestamp", time.monotonic()),
                                required_skills=data.get("required_skills", []),
                                priority=data.get("priority", "normal"),
                                metadata=data.get("metadata", {}),
                            )
                            if (
                                current_tags
                                and msg.required_skills
                                and not current_tags.intersection(set(msg.required_skills))
                            ):
                                continue
                            try:
                                await current_handler(msg)
                            except Exception:
                                logger.exception("Redis listener handler error")
                except asyncio.CancelledError:
                    break
                except Exception:
                    if self._shutdown:
                        break
                    logger.exception(f"Redis listener for topic '{topic}' disconnected, reconnecting in {backoff}s")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)  # 上限30秒

        task = asyncio.create_task(listener())
        self._listener_tasks[sub_id] = task
        return sub_id

    async def unsubscribe(self, topic: str, subscriber_id: str) -> None:
        async with self._lock:
            self._subscriptions.pop(subscriber_id, None)
        task = self._listener_tasks.pop(subscriber_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def update_subscription_tags(self, topic, subscriber_id, tags):
        async with self._lock:
            if subscriber_id in self._subscriptions:
                t, h, _ = self._subscriptions[subscriber_id]
                self._subscriptions[subscriber_id] = (t, h, tags)

    async def register_intent(self, intent_id: str, timeout: float) -> None:
        await self._init_intent_mode()
        async with self._lock:
            if intent_id in self._local_intents:
                return
            local_task = asyncio.create_task(self._local_intent_timeout(intent_id, timeout))
            self._local_intents[intent_id] = local_task

        if not self._use_local_intent_timeout:
            await self.redis.setex(f"{self.prefix}:intent:{intent_id}", int(timeout), "active")

    async def complete_intent(self, intent_id, success=True):
        async with self._lock:
            task = self._local_intents.pop(intent_id, None)
        if task and not task.done():
            task.cancel()
        if not self._use_local_intent_timeout:
            await self.redis.delete(f"{self.prefix}:intent:{intent_id}")

    async def is_intent_active(self, intent_id):
        async with self._lock:
            if intent_id in self._local_intents:
                return True
        if not self._use_local_intent_timeout:
            return await self.redis.exists(f"{self.prefix}:intent:{intent_id}") > 0
        return False

    async def _monitor_intent_expiry(self):
        """监听 Redis 键空间过期事件，并检查本地意图缓存，彻底消除竞态虚假超时"""
        channel = f"__keyevent@{self.db}__:expired"
        while not self._shutdown:
            try:
                async with self.redis.pubsub() as pubsub:
                    await pubsub.psubscribe(channel)
                    async for message in pubsub.listen():
                        if self._shutdown:
                            break
                        if message["type"] != "pmessage":
                            continue
                        expired = message["data"].decode() if isinstance(message["data"], bytes) else message["data"]
                        if expired.startswith(f"{self.prefix}:intent:"):
                            intent_id = expired[len(f"{self.prefix}:intent:") :]
                            # 若本地意图缓存中已不存在该 intent_id，说明已在过期前被完成，忽略虚假超时
                            async with self._lock:
                                if intent_id not in self._local_intents:
                                    continue
                                # 同时清理本地定时器，避免后续重复触发
                                task = self._local_intents.pop(intent_id, None)
                                if task and not task.done():
                                    task.cancel()
                            await self.publish(
                                "intent.timeout",
                                ECM(trace_id=intent_id, intent="intent.timeout", intent_id=intent_id, emitter="bus"),
                            )
            except Exception:
                logger.exception("Keyspace monitor connection lost, reconnecting...")
                await asyncio.sleep(1)

    async def _local_intent_timeout(self, intent_id, timeout):
        try:
            await asyncio.sleep(timeout)
        except asyncio.CancelledError:
            return
        async with self._lock:
            task = self._local_intents.pop(intent_id, None)
        if task is not None:
            await self.publish(
                "intent.timeout", ECM(trace_id=intent_id, intent="intent.timeout", intent_id=intent_id, emitter="bus")
            )

    async def close(self):
        self._shutdown = True
        for t in self._listener_tasks.values():
            t.cancel()
        await asyncio.gather(*self._listener_tasks.values(), return_exceptions=True)
        if self._intent_monitor_task:
            self._intent_monitor_task.cancel()
            try:
                await self._intent_monitor_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            local_tasks = list(self._local_intents.values())
            self._local_intents.clear()
        for t in local_tasks:
            t.cancel()
        await asyncio.gather(*local_tasks, return_exceptions=True)
        await self.redis.aclose()
