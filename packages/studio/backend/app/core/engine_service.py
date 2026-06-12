"""HiveFlow Studio - Engine Service Wrapper"""
import asyncio
import json
import logging
import time
import uuid
import sys
import os
from typing import Any, Callable, Dict, List, Optional

# Add HiveFlow Core package to path (packages/core)
_packages_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
_hiveflow_core = os.path.join(_packages_dir, "core")
if _hiveflow_core not in sys.path:
    sys.path.insert(0, _hiveflow_core)

from hiveflow import (
    HiveFlow, HiveFlowConfig, ECM, Expectation, Capability, MISSING, TaskGraph,
    AbortExecutionException, KnowledgeBaseManager, MCPPluginManager,
    HITLManager, HITLAction, HITLStatus, HITLGate,
    CheckpointManager, MemoryCheckpointBackend,
    InputGuard, OutputValidator,
)
from hiveflow.scheduler import (
    SelectionStrategy, LeastLoadedStrategy, AuctionStrategy, GlobalLoadAwareStrategy
)
from hiveflow.blackboard import OrchestratorReadonlyView

logger = logging.getLogger(__name__)

# Skill workers registered by app.core.agent_runtime.build_hive_mind_app
STUDIO_AGENT_WORKER_IDS = ("studio-summarize", "studio-general", "studio-final-answer")


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
        self._node_execution_stats: List[dict] = []  # per-node duration samples
        self._agent_load_history: Dict[str, List[dict]] = {}
        self._agent_recent_tasks: Dict[str, List[dict]] = {}
        self._ws_connected = False  # WebSocket connection status
        self._metrics_exporter = None  # Prometheus metrics exporter
        self._start_time = time.time()
        self._kb_manager: Optional[KnowledgeBaseManager] = None
        self._plugin_manager: Optional[MCPPluginManager] = None
        self._hitl_manager: Optional[HITLManager] = None
        self._checkpoint_manager: Optional[CheckpointManager] = None
        self._input_guard: Optional[InputGuard] = None
        self._output_validator: Optional[OutputValidator] = None
        self.runtime_mode: str = os.environ.get("HIVEFLOW_RUNTIME", "core").lower()
        self._hive_mind = None
        self._replay_debugger = None

    def set_metrics_exporter(self, exporter):
        """设置 Prometheus 指标导出器"""
        self._metrics_exporter = exporter

    async def start(self) -> None:
        if self._running:
            return
        self.engine = HiveFlow(self.config)
        await self.engine.start()
        self._kb_manager = KnowledgeBaseManager()
        self._plugin_manager = MCPPluginManager()
        self._hitl_manager = HITLManager()
        self._checkpoint_manager = CheckpointManager(MemoryCheckpointBackend())
        self._input_guard = InputGuard()
        self._output_validator = OutputValidator()
        self._hitl_manager.register_callback(self._on_hitl_gate_created)
        if self.runtime_mode == "agent":
            try:
                await self._start_agent_runtime()
            except Exception:
                logger.exception("Agent runtime failed to start at boot; falling back to core mode")
                self.runtime_mode = "core"
                await self._teardown_agent_workers()
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
        if self._hive_mind:
            await self._shutdown_agent_runtime()
        if self.engine:
            await self.engine.shutdown()
        if self._metrics_exporter:
            self._metrics_exporter.update_gauge("active_workers", 0)
        logger.info("HiveFlow engine shut down")

    async def _teardown_agent_workers(self) -> None:
        """Remove Studio skill workers from the shared HiveFlow cell."""
        if not self.engine:
            return
        for agent_id in STUDIO_AGENT_WORKER_IDS:
            try:
                await self.engine.cell.stop_worker(agent_id)
            except Exception:
                logger.debug("stop_worker skipped for %s", agent_id, exc_info=True)

    async def _shutdown_agent_runtime(self) -> None:
        if self._hive_mind:
            await self._hive_mind.shutdown()
            self._hive_mind = None
        await self._teardown_agent_workers()

    async def _start_agent_runtime(self) -> None:
        await self._teardown_agent_workers()
        from app.core.agent_runtime import build_hive_mind_app
        self._hive_mind = await build_hive_mind_app(self)
        logger.info("HiveMind agent runtime started")

    async def reload_agent_runtime(self) -> dict:
        """Rebuild HiveMind with latest LLM settings."""
        if self.runtime_mode != "agent":
            raise RuntimeError("Agent runtime is not active")
        if not self._running:
            raise RuntimeError("Engine not running")
        await self._shutdown_agent_runtime()
        await self._start_agent_runtime()
        from app.core.llm_settings import get_agent_settings_view
        return get_agent_settings_view(agent_active=True)

    async def run_agent_query(self, query: str, conversation_id: Optional[str] = None) -> dict:
        if self.runtime_mode != "agent" or not self._hive_mind:
            raise RuntimeError("Agent runtime is not active. Set HIVEFLOW_RUNTIME=agent")
        return await self._hive_mind.run_query(query, conversation_id)

    async def run_agent_plan_only(self, query: str, conversation_id: Optional[str] = None) -> dict:
        if self.runtime_mode != "agent" or not self._hive_mind:
            raise RuntimeError("Agent runtime is not active. Set HIVEFLOW_RUNTIME=agent")
        return await self._hive_mind.plan_only(query, conversation_id)

    async def run_agent_execute_plan(
        self,
        plan: dict,
        query: str = "",
        conversation_id: Optional[str] = None,
    ) -> dict:
        if self.runtime_mode != "agent" or not self._hive_mind:
            raise RuntimeError("Agent runtime is not active. Set HIVEFLOW_RUNTIME=agent")
        return await self._hive_mind.execute_plan(plan, query, conversation_id)

    async def register_mcp_as_skills(self, plugin_id: str) -> List[str]:
        if not self._hive_mind:
            raise RuntimeError("Agent runtime is not active")
        return await self._hive_mind.register_mcp_skills(self.get_plugin_manager(), [plugin_id])

    async def auto_register_mcp_skills(self, plugin_id: str) -> List[str]:
        """Register MCP tools as skills when Agent runtime is active."""
        if self.runtime_mode != "agent" or not self._hive_mind:
            return []
        return await self.register_mcp_as_skills(plugin_id)

    def get_runtime_info(self) -> dict:
        return {
            "runtime_mode": self.runtime_mode,
            "agent_active": self._hive_mind is not None,
            "skills": list(self._hive_mind.config.skill_registry.keys()) if self._hive_mind else [],
        }

    async def set_runtime_mode(self, mode: str) -> dict:
        mode = mode.lower()
        if mode not in ("core", "agent"):
            raise ValueError("mode must be 'core' or 'agent'")
        if mode == self.runtime_mode and (
            (mode == "agent" and self._hive_mind is not None)
            or (mode == "core" and self._hive_mind is None)
        ):
            return self.get_runtime_info()
        await self._shutdown_agent_runtime()
        self.runtime_mode = mode
        if mode == "agent" and self._running:
            try:
                await self._start_agent_runtime()
            except Exception as exc:
                self.runtime_mode = "core"
                await self._teardown_agent_workers()
                raise RuntimeError(f"Failed to start agent runtime: {exc}") from exc
        return self.get_runtime_info()

    def get_replay_debugger(self):
        if self._hive_mind:
            return self._hive_mind.get_replay_debugger()
        try:
            from replay import ReplayDebugger
        except ImportError:
            _agent_dir = os.path.join(_packages_dir, "agent")
            if _agent_dir not in sys.path:
                sys.path.insert(0, _agent_dir)
            from replay import ReplayDebugger
        if self._replay_debugger is None:
            self._replay_debugger = ReplayDebugger(
                self.engine.blackboard,
                self.get_checkpoint_manager(),
            )
        return self._replay_debugger

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
        self._record_agent_load_snapshot()
        caps = self.engine.scheduler._capabilities.values()
        agents = []
        for cap in caps:
            agents.append(self._serialize_agent_capability(cap))
        return agents

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        cap = self.engine.scheduler._capabilities.get(agent_id)
        if cap is None:
            return None
        self._record_agent_load_snapshot()
        return self._serialize_agent_capability(cap)

    def _serialize_agent_capability(self, cap: Capability) -> dict:
        return {
            "agent_id": cap.agent_id,
            "skills": list(cap.skills),
            "load": cap.load,
            "pending_tasks": cap.pending_tasks,
            "state": cap.state,
            "read_keys": list(cap.read_keys),
            "write_keys": list(cap.write_keys),
            "load_history": list(self._agent_load_history.get(cap.agent_id, [])),
            "recent_tasks": list(self._agent_recent_tasks.get(cap.agent_id, [])),
        }

    def _record_agent_load_snapshot(self) -> None:
        if not self.engine:
            return
        now = time.time()
        hour_ago = now - 3600
        for cap in self.engine.scheduler._capabilities.values():
            history = self._agent_load_history.setdefault(cap.agent_id, [])
            history.append({"time": now, "load": cap.load})
            self._agent_load_history[cap.agent_id] = [
                point for point in history if point.get("time", 0) >= hour_ago
            ][-120:]

    def _record_agent_task(
        self,
        agent_id: str,
        intent_id: str,
        status: str,
        payload: Optional[dict] = None,
    ) -> None:
        if not agent_id:
            return
        payload = payload or {}
        duration_ms = float(payload.get("duration_ms") or payload.get("duration") or 0)
        if "duration_ms" in (payload or {}) or duration_ms > 100:
            duration_sec = duration_ms / 1000.0
        else:
            duration_sec = duration_ms
        task_status = "success" if status == "completed" else "failed" if status == "failed" else "timeout"
        tasks = self._agent_recent_tasks.setdefault(agent_id, [])
        tasks.append({
            "intent_id": intent_id,
            "status": task_status,
            "timestamp": time.time(),
            "duration": round(duration_sec, 3),
        })
        self._agent_recent_tasks[agent_id] = tasks[-20:]

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
        enable_guard: bool = True,
        enable_checkpoint: bool = True,
    ) -> dict:
        """Execute a workflow (dag or dynamic) and return results."""
        if not self._running:
            raise RuntimeError("Engine not running")

        start_time = time.monotonic()
        if self._metrics_exporter:
            self._metrics_exporter.update_counter("workflows_total")

        prepared_graph = self._prepare_graph(
            wf_id, graph, enable_guard=enable_guard, enable_checkpoint=enable_checkpoint
        )

        async def _run():
            if mode == "dynamic":
                results = await self.engine.dynamic_orchestrator.execute(
                    prepared_graph, global_timeout=global_timeout
                )
            else:
                results = await self.engine.dag_orchestrator.execute(prepared_graph)
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

    def _prepare_graph(
        self,
        wf_id: str,
        graph: TaskGraph,
        enable_guard: bool = True,
        enable_checkpoint: bool = True,
    ) -> TaskGraph:
        """Wrap node tasks with HITL, guard, and checkpoint hooks."""
        prepared: TaskGraph = {}
        for node_id, node in graph.items():
            original_task = node["task"]
            variant = node.get("variant", "task")
            hitl_config = node.get("hitl_config") or {}

            async def wrapped_task(
                deps,
                view,
                _orig=original_task,
                _nid=node_id,
                _variant=variant,
                _hitl=hitl_config,
                _node=node,
            ):
                await self._broadcast_workflow_node(wf_id, _nid, "running")
                try:
                    if enable_guard:
                        self._apply_input_guard(deps)

                    if _variant == "hitl":
                        t0 = time.monotonic()
                        result = await self._run_hitl_node(wf_id, _nid, _hitl, deps)
                    else:
                        t0 = time.monotonic()
                        result = await _orig(deps, view)

                    self.record_node_execution(_nid, (time.monotonic() - t0) * 1000, wf_id)

                    if enable_guard:
                        result = self._apply_output_guard(result)

                    if enable_checkpoint:
                        await self._save_node_checkpoint(wf_id, _nid, deps, result)

                    await self._broadcast_workflow_node(wf_id, _nid, "completed", result)
                    return result
                except Exception as exc:
                    await self._broadcast_workflow_node(wf_id, _nid, "failed", str(exc))
                    raise

            prepared[node_id] = {**node, "task": wrapped_task}
        return prepared

    async def _broadcast_workflow_node(
        self,
        wf_id: str,
        node_id: str,
        status: str,
        result=None,
    ) -> None:
        try:
            from app.core.ws_manager import manager
            await manager.broadcast({
                "type": "workflow.status",
                "wid": wf_id,
                "node": node_id,
                "status": status,
                "result": result,
            })
        except Exception:
            logger.debug("workflow status broadcast skipped", exc_info=True)

    async def _run_hitl_node(
        self,
        wf_id: str,
        node_id: str,
        hitl_config: dict,
        deps: dict,
    ) -> dict:
        action_name = hitl_config.get("action", "approval")
        try:
            action = HITLAction(action_name)
        except ValueError:
            action = HITLAction.APPROVAL

        gate = await self._hitl_manager.create_gate(
            workflow_id=wf_id,
            node_id=node_id,
            action=action,
            prompt=hitl_config.get("prompt", "Approve to continue workflow"),
            context={"deps": self._json_safe(deps), **hitl_config.get("context", {})},
            timeout_seconds=float(hitl_config.get("timeout_seconds", 300)),
            on_timeout=hitl_config.get("on_timeout", "fail"),
        )

        resolved = await self._hitl_manager.wait_for_response(gate.gate_id)
        if resolved.status in (HITLStatus.REJECTED, HITLStatus.TIMED_OUT, HITLStatus.CANCELLED):
            raise AbortExecutionException(
                f"HITL gate blocked at node '{node_id}': {resolved.status.value}"
            )

        return {
            "gate_id": gate.gate_id,
            "status": resolved.status.value,
            "response": resolved.human_response,
            "comment": resolved.human_comment,
        }

    def _json_safe(self, value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)

    def _apply_input_guard(self, deps: dict) -> None:
        if not self._input_guard:
            return
        for key, val in deps.items():
            if val is MISSING:
                continue
            if isinstance(val, str):
                result = self._input_guard.check(val)
                if not result.passed:
                    raise AbortExecutionException(f"Input guard blocked dependency '{key}': {result.reason}")

    def _apply_output_guard(self, result: Any) -> Any:
        if not self._output_validator:
            return result
        if isinstance(result, str):
            check = self._output_validator.validate(result)
            if not check.passed:
                raise AbortExecutionException(f"Output guard blocked: {check.reason}")
            return check.sanitized_output if check.sanitized_output is not None else result
        return result

    async def _save_node_checkpoint(
        self,
        wf_id: str,
        node_id: str,
        deps: dict,
        result: Any,
    ) -> None:
        if not self._checkpoint_manager:
            return
        cp_id = await self._checkpoint_manager.save_checkpoint(
            workflow_id=wf_id,
            state={
                "node_id": node_id,
                "deps": self._json_safe({k: v for k, v in deps.items() if v is not MISSING}),
                "result": self._json_safe(result),
            },
            metadata={"node_id": node_id},
        )
        if self._broadcast_fn:
            await self._broadcast_fn("workflow.checkpoint", {
                "workflow_id": wf_id,
                "node_id": node_id,
                "checkpoint_id": cp_id,
            })

    async def _on_hitl_gate_created(self, gate: HITLGate) -> None:
        if self._broadcast_fn:
            await self._broadcast_fn("hitl.pending", {
                "gate_id": gate.gate_id,
                "workflow_id": gate.workflow_id,
                "node_id": gate.node_id,
                "prompt": gate.prompt,
                "action": gate.action.value,
                "context": gate.context,
            })

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
            "trace_id": intent_id,
            "intent": intent_type,
            "emitter": emitter,
            "status": status,
            "timestamp": time.time(),
        }
        self._intent_history.append(entry)

    def record_node_execution(
        self,
        node_name: str,
        duration_ms: float,
        intent_id: str = "",
    ) -> None:
        """Record a single node execution sample for analytics."""
        self._node_execution_stats.append({
            "node_name": node_name,
            "duration_ms": float(duration_ms),
            "intent_id": intent_id,
            "timestamp": time.time(),
        })
        if len(self._node_execution_stats) > 5000:
            self._node_execution_stats = self._node_execution_stats[-3000:]

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
            self._record_agent_task(msg.emitter, msg.intent_id, "completed", msg.payload)
            if self._broadcast_fn:
                await self._broadcast_fn("task.completed", {
                    "intent_id": msg.intent_id,
                    "emitter": msg.emitter,
                    "payload": msg.payload,
                    "trace_id": msg.trace_id,
                })

        async def _on_task_failed(msg: ECM):
            self.record_intent(msg.intent_id, msg.intent, msg.emitter, "failed")
            self._record_agent_task(msg.emitter, msg.intent_id, "failed", msg.payload)
            if self._broadcast_fn:
                await self._broadcast_fn("task.failed", {
                    "intent_id": msg.intent_id,
                    "emitter": msg.emitter,
                    "payload": msg.payload,
                    "trace_id": msg.trace_id,
                })

        async def _on_intent_timeout(msg: ECM):
            self.record_intent(msg.intent_id, msg.intent, msg.emitter, "timeout")
            self._record_agent_task(msg.emitter, msg.intent_id, "timeout", msg.payload)
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

    async def set_strategy(self, strategy: SelectionStrategy):
        await self.engine.set_strategy(strategy)

    def get_scheduler_settings(self) -> dict:
        sched = self.engine.scheduler
        strat = sched.strategy
        strategy_name = "auction" if isinstance(strat, AuctionStrategy) else "least_loaded"
        auction_timeout = getattr(strat, "auction_timeout", sched.config.auction_timeout)
        return {
            "strategy": strategy_name,
            "auction_timeout": float(auction_timeout),
        }

    async def set_scheduler_settings(self, strategy: str, auction_timeout: float = 5.0) -> None:
        if strategy == "auction":
            await self.set_strategy(
                AuctionStrategy(self.engine.bus, auction_timeout=auction_timeout)
            )
        else:
            await self.set_strategy(LeastLoadedStrategy())
        self.engine.scheduler.config.auction_timeout = auction_timeout
        self.engine.scheduler.config.selection_strategy = strategy

    # ========== Analytics (missing methods needed by analytics.py) ==========

    def get_workflow_stats(self) -> dict:
        """获取工作流统计数据"""
        completed = self.engine.metrics._counters.get("workflows_completed", 0)
        failed = self.engine.metrics._counters.get("workflows_failed", 0)
        total = completed + failed
        success_rate = (completed / total * 100) if total > 0 else 0
        durations = [
            float(e.get("duration_ms", 0) or 0)
            for e in self._node_execution_stats
            if float(e.get("duration_ms", 0) or 0) > 0
        ]
        avg_duration = round(sum(durations) / len(durations)) if durations else 0
        return {
            "total_executions": total,
            "success_rate": round(success_rate, 2),
            "avg_duration": avg_duration,
        }

    def get_agent_stats(self) -> dict:
        """获取Agent统计数据"""
        caps = self.engine.scheduler._capabilities.values()
        active = sum(1 for c in caps if c.state == "running")
        tasks_completed = self.engine.metrics._counters.get("workflows_completed", 0)
        return {
            "total": len(caps),
            "active": active,
            "tasks_completed": tasks_completed,
        }

    def get_workflow_trend(self, days: int = 7) -> list:
        """Aggregate intent history into daily execution trend buckets."""
        import datetime
        from collections import OrderedDict

        now = time.time()
        day_seconds = 86400
        buckets: OrderedDict[str, dict] = OrderedDict()
        for i in range(days):
            day = datetime.date.fromtimestamp(now - (days - 1 - i) * day_seconds)
            key = day.isoformat()
            buckets[key] = {
                "date": key,
                "executions": 0,
                "successes": 0,
                "failures": 0,
                "avg_duration": 0,
            }

        for entry in self._intent_history:
            ts = entry.get("timestamp", 0)
            if ts < now - days * day_seconds:
                continue
            day_key = datetime.date.fromtimestamp(ts).isoformat()
            if day_key not in buckets:
                continue
            buckets[day_key]["executions"] += 1
            status = entry.get("status", "")
            if status == "completed":
                buckets[day_key]["successes"] += 1
            elif status == "failed":
                buckets[day_key]["failures"] += 1
            duration_ms = float(entry.get("duration_ms", 0) or 0)
            if duration_ms > 0:
                buckets[day_key]["_duration_sum"] = buckets[day_key].get("_duration_sum", 0.0) + duration_ms
                buckets[day_key]["_duration_count"] = buckets[day_key].get("_duration_count", 0) + 1

        for entry in self._node_execution_stats:
            ts = entry.get("timestamp", 0)
            if ts < now - days * day_seconds:
                continue
            day_key = datetime.date.fromtimestamp(ts).isoformat()
            if day_key not in buckets:
                continue
            duration_ms = float(entry.get("duration_ms", 0) or 0)
            if duration_ms <= 0:
                continue
            buckets[day_key]["_duration_sum"] = buckets[day_key].get("_duration_sum", 0.0) + duration_ms
            buckets[day_key]["_duration_count"] = buckets[day_key].get("_duration_count", 0) + 1

        for bucket in buckets.values():
            duration_count = bucket.pop("_duration_count", 0)
            duration_sum = bucket.pop("_duration_sum", 0.0)
            if duration_count > 0:
                bucket["avg_duration"] = round(duration_sum / duration_count)

        return list(buckets.values())

    def get_node_duration_stats(self, limit: int = 20) -> list:
        """Node duration rankings from recorded executions, audit keys, and Prometheus histograms."""
        from collections import defaultdict

        stats: dict[str, dict] = defaultdict(
            lambda: {"call_count": 0, "total_duration": 0.0, "max_duration": 0.0, "min_duration": float("inf")},
        )

        for entry in self._node_execution_stats:
            name = entry.get("node_name", "unknown")
            dur = float(entry.get("duration_ms", 0))
            stats[name]["call_count"] += 1
            stats[name]["total_duration"] += dur
            stats[name]["max_duration"] = max(stats[name]["max_duration"], dur)
            stats[name]["min_duration"] = min(stats[name]["min_duration"], dur)

        try:
            audit = getattr(self.engine.blackboard, "_audit_log", []) or []
            for row in audit[-500:]:
                key = str(row.get("key", ""))
                if ":result:" not in key and "hivemind:result:" not in key:
                    continue
                parts = key.split(":")
                node_name = parts[-1] if len(parts) >= 3 else key
                stats[node_name]["call_count"] += 1
                stats[node_name]["total_duration"] += 100.0
        except Exception:
            pass

        if self._metrics_exporter:
            prom = getattr(self._metrics_exporter, "_histograms", {}) or {}
            self._merge_histogram_node_stats(stats, prom)

        rankings = []
        for name, s in stats.items():
            if s["call_count"] == 0:
                continue
            avg = s["total_duration"] / s["call_count"]
            min_d = s["min_duration"] if s["min_duration"] != float("inf") else avg * 0.3
            rankings.append({
                "node_name": name,
                "avg_duration": round(avg),
                "max_duration": round(s["max_duration"] or avg * 1.5),
                "min_duration": round(min_d),
                "call_count": s["call_count"],
            })
        return sorted(rankings, key=lambda x: x["avg_duration"], reverse=True)[:limit]

    def _merge_histogram_node_stats(self, stats: dict, histograms: dict) -> None:
        """Merge Prometheus-style histogram buckets into node stats."""
        for metric_name, data in histograms.items():
            if "node" not in metric_name.lower() and "workflow" not in metric_name.lower():
                continue
            node_name = metric_name.replace("_duration_seconds", "").replace("_", " ")
            count = data.get("count", 0) if isinstance(data, dict) else 0
            total = data.get("sum", 0) if isinstance(data, dict) else 0
            if count:
                ms = float(total) * 1000 / count if total else 500
                stats[node_name]["call_count"] += int(count)
                stats[node_name]["total_duration"] += ms * int(count)

    async def get_prometheus_analytics(self) -> dict:
        """Merge Prometheus / internal metrics with node duration stats."""
        metrics_json = await self.get_metrics_json()
        histograms = metrics_json.get("histograms", {})
        node_stats = self.get_node_duration_stats()
        if histograms:
            from collections import defaultdict
            stats: dict = defaultdict(
                lambda: {"call_count": 0, "total_duration": 0.0, "max_duration": 0.0, "min_duration": float("inf")},
            )
            for n in node_stats:
                stats[n["node_name"]] = {
                    "call_count": n["call_count"],
                    "total_duration": n["avg_duration"] * n["call_count"],
                    "max_duration": n["max_duration"],
                    "min_duration": n["min_duration"],
                }
            self._merge_histogram_node_stats(stats, histograms)
            merged = []
            for name, s in stats.items():
                if not s["call_count"]:
                    continue
                avg = s["total_duration"] / s["call_count"]
                merged.append({
                    "node_name": name,
                    "avg_duration": round(avg),
                    "max_duration": round(s["max_duration"] or avg * 1.5),
                    "min_duration": round(s["min_duration"] if s["min_duration"] != float("inf") else avg * 0.3),
                    "call_count": s["call_count"],
                })
            node_stats = sorted(merged, key=lambda x: x["avg_duration"], reverse=True)
        return {
            "metrics": metrics_json,
            "nodes": node_stats,
            "counters": metrics_json.get("counters", {}),
        }

    def get_agent_performance(self) -> list:
        """获取Agent性能数据"""
        self._record_agent_load_snapshot()
        caps = self.engine.scheduler._capabilities.values()
        agents = []
        for cap in caps:
            agents.append({
                "agent_id": cap.agent_id,
                "load": cap.load,
                "pending_tasks": cap.pending_tasks,
                "state": cap.state,
                "skills": list(cap.skills),
                "load_history": list(self._agent_load_history.get(cap.agent_id, [])),
                "recent_tasks": list(self._agent_recent_tasks.get(cap.agent_id, [])),
            })
        return agents

    def get_recent_errors(self, limit: int = 50) -> list:
        """获取最近的错误"""
        return [
            e for e in self._intent_history[-limit:]
            if e.get("status") == "failed"
        ]

    def get_blackboard_stats(self) -> dict:
        """获取黑板统计数据"""
        try:
            backend = self.engine.blackboard._backend
            if hasattr(backend, '_data'):
                total_keys = len(backend._data)
            else:
                total_keys = 0
        except Exception:
            total_keys = 0
        return {
            "total_keys": total_keys,
            "total_writes": self.engine.metrics._counters.get("blackboard_writes", 0),
            "total_reads": self.engine.metrics._counters.get("blackboard_reads", 0),
            "hit_rate": 0,  # placeholder
        }

    def get_kb_manager(self) -> KnowledgeBaseManager:
        if self._kb_manager is None:
            self._kb_manager = KnowledgeBaseManager()
        return self._kb_manager

    def get_plugin_manager(self) -> MCPPluginManager:
        if self._plugin_manager is None:
            self._plugin_manager = MCPPluginManager()
        return self._plugin_manager

    def get_hitl_manager(self) -> HITLManager:
        if self._hitl_manager is None:
            self._hitl_manager = HITLManager()
        return self._hitl_manager

    def get_checkpoint_manager(self) -> CheckpointManager:
        if self._checkpoint_manager is None:
            self._checkpoint_manager = CheckpointManager(MemoryCheckpointBackend())
        return self._checkpoint_manager


# Global singleton
engine_service: Optional[EngineService] = None


def get_engine() -> EngineService:
    global engine_service
    if engine_service is None:
        engine_service = EngineService()
    return engine_service
