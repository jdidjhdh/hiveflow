import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

try:
    from . import ECM, Capability
    from .bus import EventBus
except ImportError:
    from bus import EventBus

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
    def __init__(self, bus: EventBus, auction_timeout=5.0):
        self.bus = bus
        self.auction_timeout = auction_timeout

    async def select(self, ecm, capabilities, worker_queues):
        required = set(ecm.required_skills)
        eligible = {
            aid: cap
            for aid, cap in capabilities.items()
            if cap.skills & required and cap.state == "running" and aid in worker_queues
        }
        if not eligible:
            return []

        auction_topic = f"auction.reply.{ecm.intent_id}"
        bids: dict[str, float] = {}
        bid_event = asyncio.Event()

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
            ordered = await LeastLoadedStrategy().select(ecm, capabilities, worker_queues)
        return ordered


class GlobalLoadAwareStrategy(SelectionStrategy):
    def __init__(self, bus: EventBus, local_weight=0.6, remote_weight=0.4, load_freshness=5.0):
        self.bus = bus
        self.local_weight = local_weight
        self.remote_weight = remote_weight
        self.load_freshness = load_freshness
        self._remote_loads: dict[str, float] = {}
        self._last_update: dict[str, float] = {}
        self._sub_id: str | None = None

    async def start(self) -> None:
        if self._sub_id is None:
            self._sub_id = await self.bus.subscribe("hiveflow:node_load", self._handle_remote_load)

    async def stop(self) -> None:
        if self._sub_id:
            await self.bus.unsubscribe("hiveflow:node_load", self._sub_id)
            self._sub_id = None

    async def _handle_remote_load(self, msg: ECM):
        agent_id = msg.emitter
        load = msg.payload.get("load", 0.0)
        self._remote_loads[agent_id] = load
        self._last_update[agent_id] = time.monotonic()

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
    default_intent_timeout: float = 60.0
    selection_strategy: str = "least_loaded"
    auction_timeout: float = 5.0


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

    def _default_strategy(self):
        if self.config.selection_strategy == "auction":
            return AuctionStrategy(self.bus, self.config.auction_timeout)
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
        await self.bus.register_intent(ecm.intent_id, self.config.default_intent_timeout)
        try:
            async with self._lock:
                caps = dict(self._capabilities)
                workers = dict(self._worker_queues)
            candidates = await self.strategy.select(ecm, caps, workers)
            if not candidates:
                await self.bus.complete_intent(ecm.intent_id, success=False)
                return False
            for agent_id in candidates:
                worker = workers.get(agent_id)
                if not worker:
                    continue
                try:
                    await worker.assign_task(ecm)
                    return True
                except RuntimeError as e:
                    logger.debug(f"Failed to assign task to {agent_id}: {e}")
                    continue
                except Exception:
                    logger.exception(f"Unexpected error assigning task to {agent_id}")
                    continue
            await self.bus.complete_intent(ecm.intent_id, success=False)
            return False
        except asyncio.CancelledError:
            await self.bus.complete_intent(ecm.intent_id, success=False)
            raise
        except Exception:
            logger.exception("Schedule error")
            await self.bus.complete_intent(ecm.intent_id, success=False)
            return False

    async def close(self):
        if self._cap_sync_sub_id:
            await self.bus.unsubscribe("hiveflow:cap_sync", self._cap_sync_sub_id)
        if self.strategy and self._strategy_started:
            await self.strategy.stop()
