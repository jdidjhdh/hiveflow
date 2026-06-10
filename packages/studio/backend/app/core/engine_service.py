"""HiveFlow Studio - Engine Service Wrapper"""
import asyncio
import json
import logging
import time
import uuid
import sys
import os
from typing import Any, Callable, Dict, List, Optional

# Add HiveFlow Core hiveflow package to path
_hiveflow_core = r"E:\HiveFlow\hiveflow-core"
if _hiveflow_core not in sys.path:
    sys.path.insert(0, _hiveflow_core)

from hiveflow import (
    HiveFlow, HiveFlowConfig, ECM, Expectation, Capability, MISSING, TaskGraph,
    AbortExecutionException
)
from hiveflow.scheduler import (
    SelectionStrategy, LeastLoadedStrategy, AuctionStrategy, GlobalLoadAwareStrategy
)
from hiveflow.blackboard import OrchestratorReadonlyView

logger = logging.getLogger(__name__)


class EngineService:
    """
    Wraps a HiveFlow engine instance and provides a high-level API
    for the Studio backend. All engine lifecycle management is handled here.
    """

    def __init__(self, config: Optional[HiveFlowConfig] = None):
        self.config = config or HiveFlowConfig()
        self.engine: Optional[HiveFlow] = None
        self._running = False
        self._event_subscriber_id: Optional[str] = None
        self._broadcast_fn = None  # will be set after ws_manager init
        self._tasks: Dict[str, asyncio.Task] = {}  # active workflow executions
        self._intent_history: List[dict] = []  # in-memory intent timeline for Studio
        self._ws_connected = False  # WebSocket connection status
        self._metrics_exporter = None  # Prometheus metrics exporter
        self._start_time = time.time()

    def set_metrics_exporter(self, exporter):
        """设置 Prometheus 指标导出器"""
        self._metrics_exporter = exporter

    async def start(self) -> None:
        if self._running:
            return
        self.engine = HiveFlow(self.config)
        await self.engine.start()
        self._running = True
        self._ws_connected = True
        if self._metrics_exporter:
            self._metrics_exporter.update_gauge("active_workers", 1)
        logger.info("HiveFlow engine started")

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        self._ws_connected = False
        for t in self._tasks.values():
            if not t.done():
                t.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        if self.engine:
            await self.engine.shutdown()
        if self._metrics_exporter:
            self._metrics_exporter.update_gauge("active_workers", 0)
        logger.info("HiveFlow engine shut down")

    # ========== Agent Management ==========

    async def create_agent(
        self,
        agent_id: str,
        skills: List[str],
        read_keys: List[str],
        write_keys: List[str],
        task_handler: Callable,
        max_queue_size: Optional[int] = None,
    ):
        return await self.engine.create_agent(
            agent_id=agent_id,
            skills=set(skills),
            read_keys=set(read_keys),
            write_keys=set(write_keys),
            task_handler=task_handler,
            max_queue_size=max_queue_size,
        )

    async def list_agents(self) -> List[dict]:
        caps = self.engine.scheduler._capabilities.values()
        agents = []
        for cap in caps:
            agents.append({
                "agent_id": cap.agent_id,
                "skills": list(cap.skills),
                "load": cap.load,
                "pending_tasks": cap.pending_tasks,
                "state": cap.state,
                "read_keys": list(cap.read_keys),
                "write_keys": list(cap.write_keys),
            })
        return agents

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        cap = self.engine.scheduler._capabilities.get(agent_id)
        if cap is None:
            return None
        return {
            "agent_id": cap.agent_id,
            "skills": list(cap.skills),
            "load": cap.load,
            "pending_tasks": cap.pending_tasks,
            "state": cap.state,
            "read_keys": list(cap.read_keys),
            "write_keys": list(cap.write_keys),
        }

    async def stop_agent(self, agent_id: str):
        await self.engine.cell.stop_worker(agent_id)

    async def drain_agent(self, agent_id: str):
        worker = self.engine.cell._workers.get(agent_id)
        if worker:
            await worker.drain()

    # ========== Workflow Execution ==========

    async def execute_workflow(
        self,
        wf_id: str,
        graph: TaskGraph,
        mode: str = "dag",
        global_timeout: Optional[float] = None,
    ) -> dict:
        """Execute a workflow (dag or dynamic) and return results."""
        if not self._running:
            raise RuntimeError("Engine not running")

        start_time = time.monotonic()
        if self._metrics_exporter:
            self._metrics_exporter.update_counter("workflows_total")

        async def _run():
            if mode == "dynamic":
                results = await self.engine.dynamic_orchestrator.execute(
                    graph, global_timeout=global_timeout
                )
            else:
                results = await self.engine.dag_orchestrator.execute(graph)
            return results

        task = asyncio.create_task(_run(), name=wf_id)
        self._tasks[wf_id] = task

        try:
            results = await task
            elapsed = time.monotonic() - start_time
            self._tasks.pop(wf_id, None)
            if self._metrics_exporter:
                self._metrics_exporter.update_counter("workflows_completed")
                self._metrics_exporter.observe_histogram("workflow_duration_seconds", elapsed)
            return {"wf_id": wf_id, "status": "completed", "results": results}
        except AbortExecutionException as e:
            self._tasks.pop(wf_id, None)
            if self._metrics_exporter:
                self._metrics_exporter.update_counter("workflows_failed")
            return {"wf_id": wf_id, "status": "aborted", "error": str(e)}
        except asyncio.CancelledError:
            self._tasks.pop(wf_id, None)
            return {"wf_id": wf_id, "status": "cancelled"}
        except Exception as e:
            self._tasks.pop(wf_id, None)
            if self._metrics_exporter:
                self._metrics_exporter.update_counter("workflows_failed")
            return {"wf_id": wf_id, "status": "failed", "error": str(e)}

    def get_workflow_status(self, wf_id: str) -> dict:
        task = self._tasks.get(wf_id)
        if task is None:
            return {"wf_id": wf_id, "status": "unknown"}
        if task.done():
            if task.cancelled():
                return {"wf_id": wf_id, "status": "cancelled"}
            exc = task.exception()
            if exc:
                return {"wf_id": wf_id, "status": "failed", "error": str(exc)}
            return {"wf_id": wf_id, "status": "completed", "result": task.result()}
        return {"wf_id": wf_id, "status": "running"}

    async def stop_workflow(self, wf_id: str) -> dict:
        task = self._tasks.pop(wf_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return {"wf_id": wf_id, "status": "cancelled"}
        return {"wf_id": wf_id, "status": "not_running"}

    # ========== Blackboard ==========

    async def get_key(self, key: str) -> Any:
        return await self.engine.blackboard.sys_get(key)

    async def set_key(self, key: str, value: Any, ttl: Optional[float] = None):
        await self.engine.blackboard.sys_put(key, value, ttl)

    async def delete_key(self, key: str):
        await self.engine.blackboard.sys_get(key)  # will raise if missing
        await self.engine.blackboard._backend.delete(key)

    async def list_keys(self) -> List[dict]:
        """List all keys currently in the blackboard."""
        try:
            keys_data = []
            backend = self.engine.blackboard._backend
            if hasattr(backend, '_data'):
                for k, v in backend._data.items():
                    keys_data.append({
                        "key": k,
                        "type": type(v).__name__,
                        "size": len(str(v)),
                    })
            return keys_data
        except Exception:
            return []

    async def get_audit_log(self, agent: str = "", key: str = "", limit: int = 50):
        audit = self.engine.blackboard._audit_log
        filtered = audit
        if agent:
            filtered = [e for e in filtered if e.get("agent") == agent]
        if key:
            filtered = [e for e in filtered if e.get("key") == key]
        return filtered[-limit:]

    # ========== Metrics ==========

    async def get_metrics(self) -> dict:
        snapshot = await self.engine.metrics.snapshot()
        caps = self.engine.scheduler._capabilities.values()
        agents_running = sum(1 for c in caps if c.state == "running")
        total_load = sum(c.load + c.pending_tasks for c in caps)
        
        # 更新 Prometheus 指标
        if self._metrics_exporter:
            self._metrics_exporter.update_gauge("active_agents", agents_running)
            self._metrics_exporter.update_gauge("queue_size", total_load)

        return {
            "counters": snapshot.get("counters", {}),
            "histograms": snapshot.get("histograms", {}),
            "active_agents": agents_running,
            "total_load": total_load,
        }

    async def get_metrics_json(self) -> Dict[str, Any]:
        """获取 JSON 格式的内部指标 (用于前端仪表板)"""
        base_metrics = await self.get_metrics()
        return {
            **base_metrics,
            "uptime_seconds": time.time() - self._start_time,
            "active_workflows": len(self._tasks),
            "ws_connected": self._ws_connected,
        }

    # ========== Events / Intents ==========

    async def publish_event(self, topic: str, msg: ECM) -> None:
        await self.engine.bus.publish(topic, msg)

    def record_intent(self, intent_id: str, intent_type: str, emitter: str, status: str = "new"):
        """Record intent event for Studio timeline."""
        entry = {
            "intent_id": intent_id,
            "intent": intent_type,
            "emitter": emitter,
            "status": status,
            "timestamp": time.time(),
        }
        self._intent_history.append(entry)

    async def get_intent_timeline(self, intent_id: str) -> List[dict]:
        if intent_id == "*":
            return self._intent_history[-100:]
        return [e for e in self._intent_history if e.get("intent_id") == intent_id]

    def get_recent_events(self, limit: int = 100) -> List[dict]:
        return self._intent_history[-limit:]

    # ========== Event Bus Subscription for Studio ==========

    async def subscribe_to_engine_events(self, broadcast_fn):
        """Subscribe to engine events and broadcast them to frontend."""
        self._broadcast_fn = broadcast_fn

        async def _on_task_completed(msg: ECM):
            self.record_intent(msg.intent_id, msg.intent, msg.emitter, "completed")
            if self._broadcast_fn:
                await self._broadcast_fn("task.completed", {
                    "intent_id": msg.intent_id,
                    "emitter": msg.emitter,
                    "payload": msg.payload,
                    "trace_id": msg.trace_id,
                })

        async def _on_task_failed(msg: ECM):
            self.record_intent(msg.intent_id, msg.intent, msg.emitter, "failed")
            if self._broadcast_fn:
                await self._broadcast_fn("task.failed", {
                    "intent_id": msg.intent_id,
                    "emitter": msg.emitter,
                    "payload": msg.payload,
                    "trace_id": msg.trace_id,
                })

        async def _on_intent_timeout(msg: ECM):
            self.record_intent(msg.intent_id, msg.intent, msg.emitter, "timeout")
            if self._broadcast_fn:
                await self._broadcast_fn("intent.timeout", {
                    "intent_id": msg.intent_id,
                    "emitter": msg.emitter,
                })

        self._event_subscriber_id = await self.engine.bus.subscribe(
            "task.completed", _on_task_completed
        )
        await self.engine.bus.subscribe("task.failed", _on_task_failed)
        await self.engine.bus.subscribe("intent.timeout", _on_intent_timeout)

    # ========== Strategy ==========

    def set_strategy(self, strategy: SelectionStrategy):
        self.engine.set_strategy(strategy)


# Global singleton
engine_service: Optional[EngineService] = None


def get_engine() -> EngineService:
    global engine_service
    if engine_service is None:
        engine_service = EngineService()
    return engine_service
