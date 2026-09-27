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

try:
    from .observability.failure_reason import FailureReason, build_failure_payload
except ImportError:
    from hiveflow.observability.failure_reason import FailureReason, build_failure_payload

_TIMEOUT_PAYLOAD = build_failure_payload(
    FailureReason.TIMEOUT,
    error="Intent execution timed out",
)


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

    async def publish_batch(self, messages: list[tuple[str, ECM]]) -> None:
        """
        Default implementation: publish each message individually.
        Override in subclasses for optimized batch publishing.
        """
        for topic, msg in messages:
            await self.publish(topic, msg)


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

    async def publish_batch(self, messages: list[tuple[str, ECM]]) -> None:
        """
        🔄 Optimized batch publishing: collect all handlers once, then dispatch.
        
        Reduces lock contention by acquiring lock only once for all messages,
        then iterating through handlers without re-acquiring.
        
        Args:
            messages: List of (topic, ECM) tuples to publish
        """
        if not messages:
            return
        
        # 🔄 Single lock acquisition for all topics
        async with self._lock:
            # Collect all handlers for all topics
            handlers_map: dict[str, list[tuple[Callable, set[str]]]] = defaultdict(list)
            for topic, msg in messages:
                subs = self._topics.get(topic, {})
                for handler, tags in subs.values():
                    # Pre-filter by skills to reduce iterations
                    if tags and msg.required_skills and not tags.intersection(set(msg.required_skills)):
                        continue
                    handlers_map[msg.intent_id].append((handler, tags, msg))
        
        # 🔄 Dispatch without lock contention
        for intent_id, handler_list in handlers_map.items():
            for handler, tags, msg in handler_list:
                try:
                    await handler(msg)
                except Exception:
                    logger.exception(f"Handler error in batch for intent {intent_id}")

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
                "intent.timeout",
                ECM(
                    trace_id=intent_id,
                    intent="intent.timeout",
                    intent_id=intent_id,
                    emitter="bus",
                    payload=dict(_TIMEOUT_PAYLOAD),
                ),
            )

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        """
        🔄 P0 FIX: Clean up all resources (topics and intents) to prevent subscriber leakage.
        
        Clears:
        - _topics: All subscription handlers
        - _intents: All pending intent timeout tasks
        """
        async with self._lock:
            # 🔄 P0 FIX: Clear topics to release subscriber references
            self._topics.clear()
            # Cancel intent timeout tasks
            tasks = list(self._intents.values())
            self._intents.clear()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("InProcessEventBus closed: cleared all topics and intents")


# ========== Redis Event Bus ==========

try:
    import redis.asyncio as aioredis
    from redis.asyncio import ConnectionPool

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    ConnectionPool = None  # type: ignore


class RedisEventBus(EventBus):
    """
    Redis-backed event bus with connection pool management.
    
    🔧 Connection Pool Enhancement:
    - Uses explicit ConnectionPool for better resource control
    - Health check mechanism to detect stale connections
    - Shared pool across all subscriptions to prevent exhaustion
    
    Args:
        redis_url: Redis connection URL
        prefix: Key prefix for all topics
        db: Redis database number
        max_connections: Maximum connections in pool (default 20)
        socket_timeout: Socket timeout in seconds
        health_check_interval: Interval for PING health checks (default 30s)
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost",
        prefix: str = "hiveflow",
        db: int = 0,
        max_connections: int = 20,  # 🔄 Increased default from 10 to 20
        socket_timeout: float = 5.0,
        health_check_interval: float = 30.0,  # 🔄 New: health check interval
    ):
        if not _REDIS_AVAILABLE:
            raise ImportError("redis required")
        
        # 🔄 Use explicit ConnectionPool for better control
        self._pool: ConnectionPool = aioredis.ConnectionPool.from_url(
            redis_url,
            db=db,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            decode_responses=False,  # Keep bytes for JSON encoding control
        )
        self.redis = aioredis.Redis(connection_pool=self._pool)
        
        self.prefix = prefix
        self.db = db
        self.max_connections = max_connections
        self.health_check_interval = health_check_interval
        
        self._lock = asyncio.Lock()
        self._sub_counter = 0
        self._listener_tasks: dict[str, asyncio.Task] = {}
        self._subscriptions: dict[str, tuple[str, Callable, set[str]]] = {}
        self._local_intents: dict[str, asyncio.Task] = {}
        self._intent_monitor_task: asyncio.Task | None = None
        self._use_local_intent_timeout: bool | None = None
        self._shutdown = False
        self._intent_mode_lock = asyncio.Lock()
        self._health_check_task: asyncio.Task | None = None  # 🔄 New: health check task
        self._last_health_check: float = 0.0  # 🔄 New: last health check timestamp

    async def _health_check_loop(self) -> None:
        """
        🔄 Background health check loop.
        
        Sends periodic PING commands to ensure connections remain alive.
        This prevents connection timeouts in idle scenarios.
        """
        while not self._shutdown:
            try:
                await asyncio.sleep(self.health_check_interval)
                if self._shutdown:
                    break
                
                # Send PING to verify connection health
                start = time.monotonic()
                await self.redis.ping()
                elapsed = time.monotonic() - start
                
                self._last_health_check = time.monotonic()
                logger.debug(f"Redis health check OK ({elapsed:.3f}s)")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Redis health check failed: {e}")
                # Don't break on health check failure - allow reconnection logic to handle it
                await asyncio.sleep(5.0)  # Backoff before retry

    async def _ensure_keyspace_notification(self) -> bool:
        try:
            config = await self.redis.config_get("notify-keyspace-events")
            val = config.get("notify-keyspace-events", "")
            if isinstance(val, bytes):
                val = val.decode()
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
        """Start the event bus, including health check loop."""
        await self._init_intent_mode()
        
        # 🔄 Start health check loop
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info(f"Redis health check started (interval={self.health_check_interval}s)")

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

    async def publish_batch(self, messages: list[tuple[str, ECM]]) -> None:
        """
        🔄 Optimized batch publishing for Redis: use pipeline to reduce network round-trips.
        
        Args:
            messages: List of (topic, ECM) tuples to publish
        """
        if not messages:
            return
        
        # Use Redis pipeline for batch publishing (single network round-trip)
        async with self.redis.pipeline() as pipe:
            for topic, msg in messages:
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
                pipe.publish(key, data)
            await pipe.execute()

    async def subscribe(self, topic: str, handler, tags=None) -> str:
        """
        Subscribe to a topic.
        
        🔄 Connection Pool Note:
        - Uses shared connection pool from self._pool
        - Each subscription creates a pubsub context but shares the pool
        - max_connections limit applies to total connections across all subscriptions
        """
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
                    # 🔄 Use connection pool for pubsub
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
                            data_bytes = message["data"]
                            data = json.loads(data_bytes if isinstance(data_bytes, bytes) else data_bytes)
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
                        expired_bytes = message["data"]
                        expired = expired_bytes.decode() if isinstance(expired_bytes, bytes) else expired_bytes
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
                                ECM(
                                    trace_id=intent_id,
                                    intent="intent.timeout",
                                    intent_id=intent_id,
                                    emitter="bus",
                                    payload=dict(_TIMEOUT_PAYLOAD),
                                ),
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
                "intent.timeout",
                ECM(
                    trace_id=intent_id,
                    intent="intent.timeout",
                    intent_id=intent_id,
                    emitter="bus",
                    payload=dict(_TIMEOUT_PAYLOAD),
                ),
            )

    async def close(self):
        """Close the event bus and release all resources."""
        self._shutdown = True
        
        # Stop health check loop
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        # Cancel all listener tasks
        for t in self._listener_tasks.values():
            t.cancel()
        await asyncio.gather(*self._listener_tasks.values(), return_exceptions=True)
        self._listener_tasks.clear()
        
        # Stop intent monitor
        if self._intent_monitor_task:
            self._intent_monitor_task.cancel()
            try:
                await self._intent_monitor_task
            except asyncio.CancelledError:
                pass
            self._intent_monitor_task = None
        
        # Cancel local intent tasks
        async with self._lock:
            local_tasks = list(self._local_intents.values())
            self._local_intents.clear()
        for t in local_tasks:
            t.cancel()
        await asyncio.gather(*local_tasks, return_exceptions=True)
        
        # Close Redis connection and pool
        await self.redis.aclose()
        await self._pool.disconnect()  # 🔄 Explicitly disconnect pool
        logger.info(f"Redis connection pool closed (max_connections={self.max_connections})")

    def get_connection_stats(self) -> dict:
        """Get connection pool statistics."""
        return {
            "max_connections": self.max_connections,
            "pool_created": self._pool.connection_kwargs.get("connection_name", "unknown"),
            "health_check_interval": self.health_check_interval,
            "last_health_check": self._last_health_check,
            "active_subscriptions": len(self._subscriptions),
        }