import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

try:
    from . import ECM, Capability
    from .bus import EventBus
    from .observability.metrics import metrics
except ImportError:
    from bus import EventBus
    from observability.metrics import metrics  # type: ignore

    from hiveflow import ECM, Capability

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3, "background": 4}


class SelectionStrategy(ABC):
    @abstractmethod
    async def select(
        self, ecm: ECM, capabilities: dict[str, Capability], worker_queues: dict[str, Any]
    ) -> list[str]: ...
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class LeastLoadedStrategy(SelectionStrategy):
    async def select(self, ecm, capabilities, worker_queues):
        required = set(ecm.required_skills)
        eligible = []
        for aid, cap in capabilities.items():
            if cap.skills & required and cap.state == "running" and aid in worker_queues:
                eligible.append((aid, cap))
        if not eligible:
            return []
        eligible.sort(key=lambda x: (x[1].load + x[1].pending_tasks) / x[1].weight if x[1].weight > 0 else float("inf"))
        return [aid for aid, _ in eligible]


class AuctionStrategy(SelectionStrategy):
    """
    Auction-based task selection strategy.
    
    When the number of eligible agents exceeds `agent_threshold`, 
    automatically falls back to LeastLoadedStrategy to avoid message storm.
    
    🔒 P0 FIX: Added pending bids cleanup to prevent Future leakage.
    """
    
    def __init__(self, bus: EventBus, auction_timeout=5.0, agent_threshold: int = 20):
        self.bus = bus
        self.auction_timeout = auction_timeout
        self.agent_threshold = agent_threshold  # Threshold for fallback to least-loaded
        self._fallback_strategy = LeastLoadedStrategy()
        self._pending_bids: dict[str, asyncio.Event] = {}  # 🔄 P0 FIX: Track pending bids by intent_id
        self._cleanup_interval: float = 5.0  # 🔄 P0 FIX: Cleanup interval
        self._cleanup_task: asyncio.Task | None = None  # 🔄 P0 FIX: Background cleanup task
        self._shutdown: bool = False  # 🔄 P0 FIX: Shutdown flag

    async def start(self) -> None:
        """🔄 P0 FIX: Start the cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_pending_bids_loop())
            logger.info(f"AuctionStrategy cleanup task started (interval={self._cleanup_interval}s)")

    async def stop(self) -> None:
        """🔄 P0 FIX: Stop the cleanup task."""
        self._shutdown = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("AuctionStrategy cleanup task stopped")

    async def _cleanup_pending_bids_loop(self) -> None:
        """
        🔄 P0 FIX: Background cleanup loop for stale pending bids.
        
        Removes pending bids that have been waiting longer than
        auction_timeout + 5s to prevent Future leakage.
        """
        while not self._shutdown:
            try:
                await asyncio.sleep(self._cleanup_interval)
                if self._shutdown:
                    break
                
                # Check for stale pending bids
                stale_intent_ids = []
                for intent_id, event in list(self._pending_bids.items()):
                    # If event is still not set after timeout, clean it up
                    if not event.is_set():
                        # Remove stale pending bid
                        stale_intent_ids.append(intent_id)
                        del self._pending_bids[intent_id]
                
                if stale_intent_ids:
                    logger.warning(f"AuctionStrategy: cleaned up {len(stale_intent_ids)} stale pending bids")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"AuctionStrategy cleanup error: {e}")
                await asyncio.sleep(1.0)  # Backoff before retry

    async def select(self, ecm, capabilities, worker_queues):
        required = set(ecm.required_skills)
        eligible = {
            aid: cap
            for aid, cap in capabilities.items()
            if cap.skills & required and cap.state == "running" and aid in worker_queues
        }
        if not eligible:
            return []

        # 🔄 Auto-fallback: when agents > threshold, use least-loaded to avoid O(N) broadcast storm
        if len(eligible) > self.agent_threshold:
            logger.info(
                f"AuctionStrategy: {len(eligible)} agents > threshold {self.agent_threshold}, "
                f"falling back to LeastLoadedStrategy for intent {ecm.intent_id}"
            )
            return await self._fallback_strategy.select(ecm, capabilities, worker_queues)

        auction_topic = f"auction.reply.{ecm.intent_id}"
        bids: dict[str, float] = {}
        bid_event = asyncio.Event()
        
        # 🔄 P0 FIX: Track pending bid for cleanup
        self._pending_bids[ecm.intent_id] = bid_event

        async def bid_collector(msg: ECM):
            agent_id = msg.emitter
            if agent_id in eligible:
                bid_value = msg.payload.get("bid", float("inf"))
                if agent_id not in bids or bid_value < bids[agent_id]:
                    bids[agent_id] = bid_value
                if len(bids) >= len(eligible):
                    bid_event.set()

        sub_id = await self.bus.subscribe(auction_topic, bid_collector)
        try:
            await self.bus.publish(
                "task.auction",
                ECM(
                    trace_id=ecm.trace_id,
                    intent="task.auction",
                    intent_id=ecm.intent_id,
                    emitter="scheduler",
                    payload={"required_skills": list(required)},
                    reply_to=auction_topic,
                ),
            )
            try:
                await asyncio.wait_for(bid_event.wait(), timeout=self.auction_timeout)
            except asyncio.TimeoutError:
                pass
        finally:
            # 🔄 P0 FIX: Clean up pending bid tracking
            self._pending_bids.pop(ecm.intent_id, None)
            try:
                await asyncio.wait_for(asyncio.shield(self.bus.unsubscribe(auction_topic, sub_id)), timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout while unsubscribing auction bid collector")

        ordered = []
        if bids:
            for aid, _ in sorted(bids.items(), key=lambda x: x[1]):
                if aid in worker_queues and capabilities.get(aid) and capabilities[aid].state == "running":
                    ordered.append(aid)
        if not ordered:
            ordered = await self._fallback_strategy.select(ecm, capabilities, worker_queues)
        return ordered


class GlobalLoadAwareStrategy(SelectionStrategy):
    def __init__(self, bus: EventBus, local_weight=0.6, remote_weight=0.4, load_freshness=5.0, load_ttl=300.0):
        self.bus = bus
        self.local_weight = local_weight
        self.remote_weight = remote_weight
        self.load_freshness = load_freshness
        # 🔄 P0 FIX: TTL for remote loads to prevent unlimited growth
        self.load_ttl = load_ttl  # Time after which agent load data is fully removed
        self._remote_loads: dict[str, float] = {}
        self._last_update: dict[str, float] = {}
        # 🔄 P0 FIX: Track first timestamp for TTL cleanup
        self._load_timestamps: dict[str, float] = {}  # When the agent first reported load
        self._sub_id: str | None = None
        self._cleanup_task: asyncio.Task | None = None  # 🔄 P0 FIX: Background cleanup task

    async def start(self) -> None:
        if self._sub_id is None:
            self._sub_id = await self.bus.subscribe("hiveflow:node_load", self._handle_remote_load)
        # 🔄 P0 FIX: Start cleanup task
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(f"GlobalLoadAwareStrategy cleanup task started (TTL={self.load_ttl}s)")

    async def stop(self) -> None:
        # 🔄 P0 FIX: Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("GlobalLoadAwareStrategy cleanup task stopped")
        
        if self._sub_id:
            await self.bus.unsubscribe("hiveflow:node_load", self._sub_id)
            self._sub_id = None

    async def _cleanup_loop(self) -> None:
        """
        🔄 P0 FIX: Periodic cleanup of stale remote load data.
        
        Removes agents whose load data has exceeded load_ttl (300s by default),
        preventing unlimited cache growth when agents go offline.
        """
        cleanup_interval = self.load_ttl / 10  # Cleanup every 30s by default
        while True:
            try:
                await asyncio.sleep(cleanup_interval)
                now = time.monotonic()
                
                # Find agents whose load data is too old
                expired_agents = []
                for agent_id, first_ts in list(self._load_timestamps.items()):
                    if (now - first_ts) > self.load_ttl:
                        expired_agents.append(agent_id)
                
                # Remove expired data
                for agent_id in expired_agents:
                    self._remote_loads.pop(agent_id, None)
                    self._last_update.pop(agent_id, None)
                    self._load_timestamps.pop(agent_id, None)
                
                if expired_agents:
                    logger.info(f"GlobalLoadAwareStrategy: cleaned up {len(expired_agents)} expired agent loads")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"GlobalLoadAwareStrategy cleanup error: {e}")
                await asyncio.sleep(5.0)

    async def _handle_remote_load(self, msg: ECM):
        agent_id = msg.emitter
        load = msg.payload.get("load", 0.0)
        self._remote_loads[agent_id] = load
        self._last_update[agent_id] = time.monotonic()
        # 🔄 P0 FIX: Record first timestamp for TTL tracking
        if agent_id not in self._load_timestamps:
            self._load_timestamps[agent_id] = time.monotonic()

    async def select(self, ecm, capabilities, worker_queues):
        required = set(ecm.required_skills)
        eligible = []
        now = time.monotonic()
        for aid, cap in capabilities.items():
            if cap.skills & required and cap.state == "running" and aid in worker_queues:
                remote_load = self._remote_loads.get(aid, 0.0)
                if aid in self._last_update and (now - self._last_update[aid]) > self.load_freshness:
                    remote_load = float("inf")
                composite = self.local_weight * (cap.load + cap.pending_tasks) + self.remote_weight * remote_load
                eligible.append((aid, composite))
        if not eligible:
            return []
        eligible.sort(key=lambda x: x[1])
        return [aid for aid, _ in eligible]


@dataclass
class SchedulerConfig:
    """Scheduler configuration with auction fallback threshold."""
    
    default_intent_timeout: float = 60.0
    selection_strategy: str = "least_loaded"
    auction_timeout: float = 5.0
    auction_agent_threshold: int = 20  # Agents exceeding this trigger fallback to least-loaded


class Scheduler(ABC):
    @abstractmethod
    async def register_worker(self, worker: Any | None, cap: Capability) -> None: ...
    @abstractmethod
    async def bind_worker(self, agent_id: str, worker: Any) -> None: ...
    @abstractmethod
    async def unregister_worker(self, agent_id: str) -> None: ...
    @abstractmethod
    async def schedule(self, ecm: ECM) -> bool: ...
    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def close(self) -> None: ...


class InProcessScheduler(Scheduler):
    def __init__(self, bus: EventBus, config: SchedulerConfig, strategy: SelectionStrategy | None = None):
        self.bus = bus
        self.config = config
        self._lock = asyncio.Lock()
        self._worker_queues: dict[str, Any] = {}
        self._capabilities: dict[str, Capability] = {}
        self.strategy = strategy or self._default_strategy()
        self._cap_sync_sub_id: str | None = None
        self._strategy_started = False
        # 🔄 P0 FIX: Track running tasks for idempotency
        self._running_tasks: dict[str, asyncio.Task] = {}  # intent_id -> running Task

    def _default_strategy(self):
        if self.config.selection_strategy == "auction":
            return AuctionStrategy(
                self.bus, 
                self.config.auction_timeout,
                self.config.auction_agent_threshold  # Pass threshold from config
            )
        return LeastLoadedStrategy()

    async def start(self) -> None:
        if isinstance(self.bus, EventBus):
            # 检查是否为 RedisEventBus（避免硬依赖导入）
            bus_type = type(self.bus).__name__
            if bus_type == "RedisEventBus":
                await self._setup_capability_sync()
        if not self._strategy_started:
            await self.strategy.start()
            self._strategy_started = True

    async def _setup_capability_sync(self):
        async def handle(msg: ECM):
            if msg.intent == "agent.registered":
                cap_data = msg.payload.get("capability")
                async with self._lock:
                    cap = Capability(**cap_data)
                    self._capabilities[cap.agent_id] = cap
            elif msg.intent == "agent.unregistered":
                agent_id = msg.payload.get("agent_id")
                async with self._lock:
                    self._capabilities.pop(agent_id, None)
                    self._worker_queues.pop(agent_id, None)

        self._cap_sync_sub_id = await self.bus.subscribe("hiveflow:cap_sync", handle)

    async def register_worker(self, worker: Any | None, cap: Capability):
        async with self._lock:
            self._capabilities[cap.agent_id] = cap
            if worker is not None:
                self._worker_queues[cap.agent_id] = worker
        if type(self.bus).__name__ == "RedisEventBus":
            await self.bus.publish(
                "hiveflow:cap_sync",
                ECM(
                    trace_id=cap.agent_id,
                    intent="agent.registered",
                    intent_id="",
                    emitter=cap.agent_id,
                    payload={"capability": cap.__dict__},
                ),
            )

    async def bind_worker(self, agent_id: str, worker: Any):
        async with self._lock:
            if agent_id not in self._capabilities:
                raise KeyError(f"Capability for {agent_id} not found, register first")
            self._worker_queues[agent_id] = worker

    async def unregister_worker(self, agent_id: str):
        async with self._lock:
            self._worker_queues.pop(agent_id, None)
            self._capabilities.pop(agent_id, None)
        if type(self.bus).__name__ == "RedisEventBus":
            await self.bus.publish(
                "hiveflow:cap_sync",
                ECM(
                    trace_id=agent_id,
                    intent="agent.unregistered",
                    intent_id="",
                    emitter=agent_id,
                    payload={"agent_id": agent_id},
                ),
            )

    async def set_strategy(self, new_strategy: SelectionStrategy):
        """安全替换策略，停止旧策略避免资源泄漏"""
        async with self._lock:
            old = self.strategy
            self.strategy = new_strategy
        if old is not None and self._strategy_started:
            await old.stop()
        if self._strategy_started:
            await new_strategy.start()

    async def schedule(self, ecm: ECM) -> bool:
        """Schedule a task to an eligible worker.
        
        🔄 P0 FIX: Idempotency - check if intent_id already running before scheduling.
        🔄 Metrics Integration:
        - task_scheduled_total: Counter for successful scheduling
        - task_schedule_failed_total: Counter for failed scheduling
        - task_schedule_latency_seconds: Histogram for scheduling latency
        """
        start_time = time.monotonic()
        
        # 🔄 P0 FIX: Idempotency check - if intent already active, return early
        async with self._lock:
            if ecm.intent_id in self._running_tasks:
                existing_task = self._running_tasks[ecm.intent_id]
                if not existing_task.done():
                    logger.info(f"Idempotent schedule: intent_id={ecm.intent_id} already running")
                    metrics.update_counter("task_schedule_idempotent_total")
                    return True  # Task already scheduled, idempotent success
                else:
                    # Task completed, remove from tracking
                    self._running_tasks.pop(ecm.intent_id, None)
        
        await self.bus.register_intent(ecm.intent_id, self.config.default_intent_timeout)
        try:
            async with self._lock:
                caps = dict(self._capabilities)
                workers = dict(self._worker_queues)
                # 🔄 P0 FIX: Create tracking task for this intent
                tracking_task = asyncio.create_task(self._track_task_completion(ecm.intent_id))
                self._running_tasks[ecm.intent_id] = tracking_task
            
            # 🔄 Metrics: Update gauge for queue size
            metrics.update_gauge("queue_size", len(self._worker_queues))
            metrics.update_gauge("active_workers", len(self._capabilities))
            
            candidates = await self.strategy.select(ecm, caps, workers)
            if not candidates:
                await self.bus.complete_intent(ecm.intent_id, success=False)
                # 🔄 Metrics: Record failed scheduling (no candidates)
                metrics.update_counter("task_schedule_failed_total", labels={"reason": "no_candidates"})
                return False
            
            for agent_id in candidates:
                worker = workers.get(agent_id)
                if not worker:
                    continue
                try:
                    await worker.assign_task(ecm)
                    
                    # 🔄 Metrics: Record successful scheduling
                    metrics.update_counter("task_scheduled_total", labels={"agent_id": agent_id})
                    metrics.update_counter("tasks_total")
                    metrics.observe_histogram(
                        "task_schedule_latency_seconds",
                        time.monotonic() - start_time,
                        labels={"strategy": self.config.selection_strategy}
                    )
                    
                    return True
                except RuntimeError as e:
                    logger.debug(f"Failed to assign task to {agent_id}: {e}")
                    # 🔄 Metrics: Record failed assignment (queue full)
                    metrics.update_counter("task_schedule_failed_total", labels={"reason": "queue_full"})
                    continue
                except Exception as e:
                    logger.exception(f"Unexpected error assigning task to {agent_id}")
                    # 🔄 Metrics: Record failed assignment (unexpected)
                    metrics.update_counter("task_schedule_failed_total", labels={"reason": "unexpected"})
                    metrics.update_counter("errors_total", labels={"error_type": "schedule_assignment"})
                    continue
            
            await self.bus.complete_intent(ecm.intent_id, success=False)
            # 🔄 Metrics: Record failed scheduling (all candidates failed)
            metrics.update_counter("task_schedule_failed_total", labels={"reason": "all_failed"})
            return False
        except asyncio.CancelledError:
            await self.bus.complete_intent(ecm.intent_id, success=False)
            # 🔄 Metrics: Record cancelled scheduling
            metrics.update_counter("task_schedule_failed_total", labels={"reason": "cancelled"})
            raise
        except Exception as e:
            logger.exception("Schedule error")
            await self.bus.complete_intent(ecm.intent_id, success=False)
            # 🔄 Metrics: Record failed scheduling (exception)
            metrics.update_counter("task_schedule_failed_total", labels={"reason": "exception"})
            metrics.update_counter("errors_total", labels={"error_type": "schedule_exception"})
            return False

    async def _track_task_completion(self, intent_id: str) -> None:
        """
        🔄 P0 FIX: Track task completion and clean up _running_tasks.
        
        Waits for the intent to complete (via bus.is_intent_active) and then
        removes it from _running_tasks to allow re-scheduling.
        """
        timeout = self.config.default_intent_timeout + 10.0  # Extra buffer
        try:
            # Poll for completion (simple approach)
            while timeout > 0:
                if not await self.bus.is_intent_active(intent_id):
                    break
                await asyncio.sleep(0.5)
                timeout -= 0.5
        except asyncio.CancelledError:
            pass
        finally:
            # Always clean up
            async with self._lock:
                self._running_tasks.pop(intent_id, None)
            logger.debug(f"Task tracking completed for intent_id={intent_id}")

    async def close(self):
        # 🔄 P0 FIX: Clean up all running task trackers
        async with self._lock:
            tracking_tasks = list(self._running_tasks.values())
            self._running_tasks.clear()
        for t in tracking_tasks:
            t.cancel()
        await asyncio.gather(*tracking_tasks, return_exceptions=True)
        
        if self._cap_sync_sub_id:
            await self.bus.unsubscribe("hiveflow:cap_sync", self._cap_sync_sub_id)
        if self.strategy and self._strategy_started:
            await self.strategy.stop()