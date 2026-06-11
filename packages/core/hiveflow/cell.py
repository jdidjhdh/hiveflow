import asyncio
import itertools
import logging
import time
import traceback
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

try:
    from . import ECM, Capability
    from .blackboard import AuditedBlackboardView, SecureBlackboard
    from .bus import EventBus
    from .scheduler import PRIORITY_ORDER, Scheduler
    from .validation import ValidationPipeline
except ImportError:
    from blackboard import AuditedBlackboardView, SecureBlackboard
    from bus import EventBus
    from scheduler import PRIORITY_ORDER, Scheduler
    from validation import ValidationPipeline

    from hiveflow import ECM, Capability

logger = logging.getLogger(__name__)


def ensure_error_writes(blackboard: SecureBlackboard, agent_id: str):
    """
    Decorator: wrap a task_handler so that if it raises an exception,
    the error is automatically written to the blackboard under a standard key.
    This prevents other workers from waiting forever for a result that will never arrive.
    """

    def decorator(fn):
        @wraps(fn)
        async def wrapper(ecm: ECM, view: AuditedBlackboardView):
            try:
                return await fn(ecm, view)
            except Exception as e:
                error_key = f"error.{ecm.intent_id}.{agent_id}"
                error_payload = {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "intent_id": ecm.intent_id,
                    "agent_id": agent_id,
                    "node": ecm.intent,
                }
                try:
                    await blackboard.sys_put(error_key, error_payload)
                except Exception:
                    logger.exception(f"Failed to write error to blackboard for {agent_id}")
                raise

        return wrapper

    return decorator


class Worker:
    def __init__(
        self,
        agent_id: str,
        skills: set[str],
        read_keys: set[str],
        write_keys: set[str],
        task_handler: Callable[[ECM, AuditedBlackboardView], Awaitable[Any]],
        blackboard: SecureBlackboard,
        bus: EventBus,
        cap: Capability,
        validation: "ValidationPipeline",
        max_queue_size: int = 0,
    ):
        self.agent_id = agent_id
        self.skills = skills
        self.read_keys = read_keys
        self.write_keys = write_keys
        self.task_handler = task_handler
        self.blackboard = blackboard
        self.bus = bus
        self.capability = cap
        self.capability.max_queue_size = max_queue_size
        self.validation = validation
        self._queue: asyncio.Queue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._seq = itertools.count()
        self._running = False
        self._task: asyncio.Task | None = None
        self._draining = False
        self._state_lock = asyncio.Lock()

    async def start(self):
        self._running = True
        self.capability.state = "running"
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            while self._running or not self._queue.empty():
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                _, _, ecm = item
                self.capability.pending_tasks -= 1
                try:
                    await self._execute_task(ecm)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(f"Worker {self.agent_id} failed to execute task")
                finally:
                    self.capability.load = max(0.0, self.capability.load - 1.0)
        except asyncio.CancelledError:
            pass

    async def _execute_task(self, ecm: ECM):
        view = self.blackboard.view_for(self.agent_id)
        success = False
        try:
            result = await self.task_handler(ecm, view)
            if ecm.expectation:
                valid = await self.validation.validate(ecm.expectation, result)
                if not valid:
                    raise ValueError(f"Validation failed for expectation on key '{ecm.expectation.state_key}'")
                await view.put(ecm.expectation.state_key, result)
            await self.bus.publish(
                "task.completed",
                ECM(
                    trace_id=ecm.trace_id,
                    intent="task.completed",
                    intent_id=ecm.intent_id,
                    emitter=self.agent_id,
                    payload={"result": result},
                ),
            )
            success = True
        except Exception as e:
            logger.exception(f"Worker {self.agent_id} task failed")
            try:
                await self.bus.publish(
                    "task.failed",
                    ECM(
                        trace_id=ecm.trace_id,
                        intent="task.failed",
                        intent_id=ecm.intent_id,
                        emitter=self.agent_id,
                        payload={"error": str(e)},
                    ),
                )
            except Exception:
                logger.exception("Failed to publish task.failed")
        finally:
            try:
                await self.bus.complete_intent(ecm.intent_id, success=success)
            except Exception:
                logger.exception("Failed to complete intent")

    async def assign_task(self, ecm: ECM) -> None:
        async with self._state_lock:
            if self._draining or not self._running:
                raise RuntimeError("Worker is draining or stopped")
            if self._queue.full():
                raise RuntimeError("Worker queue full, task rejected")
            self.capability.load += 1.0
            self.capability.pending_tasks += 1
            try:
                priority_order = PRIORITY_ORDER.get(ecm.priority, 2)
                self._queue.put_nowait((priority_order, next(self._seq), ecm))
            except asyncio.QueueFull:
                self.capability.load -= 1.0
                self.capability.pending_tasks -= 1
                raise

    async def drain(self):
        async with self._state_lock:
            self._draining = True
        deadline = time.monotonic() + 30.0
        while not self._queue.empty():
            if time.monotonic() > deadline:
                logger.error(f"Worker {self.agent_id} drain timeout, forcefully stopping")
                break
            await asyncio.sleep(0.1)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                _, _, ecm = item
                self.capability.pending_tasks -= 1
                self.capability.load = max(0.0, self.capability.load - 1.0)
                if await self.bus.is_intent_active(ecm.intent_id):
                    try:
                        await self.bus.complete_intent(ecm.intent_id, success=False)
                    except Exception:
                        logger.exception("Failed to complete intent during stop")
            except asyncio.QueueEmpty:
                break


class Cell:
    def __init__(
        self,
        bus: EventBus,
        blackboard: SecureBlackboard,
        scheduler: Scheduler,
        validation: "ValidationPipeline",
        default_max_queue_size: int = 0,
    ):
        self.bus = bus
        self.blackboard = blackboard
        self.scheduler = scheduler
        self.validation = validation
        self.default_max_queue_size = default_max_queue_size
        self._workers: dict[str, Worker] = {}
        self._lock = asyncio.Lock()
        self._shutting_down = False

    async def create_worker(
        self,
        agent_id: str,
        skills: set[str],
        read_keys: set[str],
        write_keys: set[str],
        handler: Callable,
        max_queue_size: int | None = None,
    ) -> Worker:
        maxsize = max_queue_size if max_queue_size is not None else self.default_max_queue_size
        async with self._lock:
            if self._shutting_down:
                raise RuntimeError("Cell is shutting down, cannot create worker")
            if agent_id in self._workers:
                raise ValueError(f"Worker {agent_id} already exists")

            cap = Capability(agent_id=agent_id, skills=skills, read_keys=read_keys, write_keys=write_keys)
            await self.blackboard.register_agent(agent_id, cap)
            try:
                await self.scheduler.register_worker(None, cap)
            except Exception:
                await self.blackboard.unregister_agent(agent_id)
                raise

            worker = None
            try:
                worker = Worker(
                    agent_id,
                    skills,
                    read_keys,
                    write_keys,
                    handler,
                    self.blackboard,
                    self.bus,
                    cap,
                    self.validation,
                    max_queue_size=maxsize,
                )
            except Exception:
                await self.blackboard.unregister_agent(agent_id)
                await self.scheduler.unregister_worker(agent_id)
                raise

            try:
                await self.scheduler.bind_worker(agent_id, worker)
                await worker.start()
            except Exception:
                await self.blackboard.unregister_agent(agent_id)
                await self.scheduler.unregister_worker(agent_id)
                raise

            self._workers[agent_id] = worker
            return worker

    async def stop_worker(self, agent_id: str):
        async with self._lock:
            worker = self._workers.pop(agent_id, None)
        if worker:
            await worker.drain()
            await worker.stop()
            await self.blackboard.unregister_agent(agent_id)
            await self.scheduler.unregister_worker(agent_id)

    async def shutdown(self):
        async with self._lock:
            self._shutting_down = True
            workers = list(self._workers.values())
            self._workers.clear()
        await asyncio.gather(*[w.drain() for w in workers], return_exceptions=True)
        await asyncio.gather(*[w.stop() for w in workers], return_exceptions=True)
