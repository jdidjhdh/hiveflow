import asyncio
import logging
import time
from graphlib import TopologicalSorter
from typing import TYPE_CHECKING, Any, Optional

from . import MISSING, AbortExecutionException, TaskGraph
from .blackboard import OrchestratorReadonlyView, SecureBlackboard
from .hitl import HITLAction, HITLStatus

if TYPE_CHECKING:
    from .checkpoint import CheckpointManager
    from .hitl import HITLManager

logger = logging.getLogger(__name__)


def _resolve_hitl_context(context: Any, deps: dict, all_results: dict) -> dict[str, Any]:
    if callable(context):
        resolved = context(deps, all_results)
        return resolved if isinstance(resolved, dict) else {"value": resolved}
    return context if isinstance(context, dict) else (context or {})


async def _run_hitl_gate(
    hitl_manager: "HITLManager",
    workflow_id: str,
    node_name: str,
    node: dict,
    deps: dict,
    all_results: dict,
) -> Any:
    hitl_cfg = node.get("hitl")
    if not hitl_cfg:
        return None

    action_raw = hitl_cfg.get("action", HITLAction.APPROVAL)
    action = HITLAction(action_raw) if isinstance(action_raw, str) else action_raw
    wf_id = hitl_cfg.get("workflow_id", workflow_id)
    context = _resolve_hitl_context(hitl_cfg.get("context"), deps, all_results)

    gate = await hitl_manager.create_gate(
        workflow_id=wf_id,
        node_id=node_name,
        action=action,
        prompt=hitl_cfg.get("prompt", f"Approve node '{node_name}'?"),
        context=context,
        timeout_seconds=hitl_cfg.get("timeout_seconds", 300.0),
        on_timeout=hitl_cfg.get("on_timeout", "fail"),
    )
    gate = await hitl_manager.wait_for_response(gate.gate_id)

    if gate.status in (HITLStatus.REJECTED, HITLStatus.TIMED_OUT):
        raise AbortExecutionException(f"HITL gate rejected or timed out for node '{node_name}' ({gate.status.value})")
    return gate.human_response


async def _save_node_checkpoint(
    checkpoint_manager: "CheckpointManager",
    workflow_id: str,
    node_name: str,
    node: dict,
    deps: dict,
    all_results: dict,
    result: Any = None,
    phase: str = "after",
) -> str | None:
    cp_cfg = node.get("checkpoint")
    if not cp_cfg:
        return None
    if cp_cfg.get("when", "after") != phase:
        return None

    wf_id = cp_cfg.get("workflow_id", workflow_id)
    state = {
        "node": node_name,
        "phase": phase,
        "deps": deps,
        "completed": dict(all_results),
    }
    if result is not MISSING and result is not None:
        state["result"] = result

    metadata = dict(cp_cfg.get("metadata") or {})
    metadata.setdefault("node", node_name)
    metadata.setdefault("phase", phase)

    return await checkpoint_manager.save_checkpoint(
        workflow_id=wf_id,
        state=state,
        metadata=metadata,
    )


class DAGOrchestrator:
    def __init__(
        self,
        blackboard: SecureBlackboard,
        metrics=None,
        logger=None,
        tracer=None,
        hitl_manager: Optional["HITLManager"] = None,
        checkpoint_manager: Optional["CheckpointManager"] = None,
        workflow_id: str | None = None,
    ):
        self.blackboard = blackboard
        self.metrics = metrics
        self.logger = logger
        self.tracer = tracer
        self.hitl_manager = hitl_manager
        self.checkpoint_manager = checkpoint_manager
        self.workflow_id = workflow_id or "default"

    async def execute(self, graph: TaskGraph) -> dict[str, Any]:
        start_time = time.monotonic()
        if self.logger:
            self.logger.info("DAG execution started", node_count=len(graph))
        if self.metrics:
            self.metrics.update_counter("workflows_total")

        try:
            sorter = TopologicalSorter({node: data.get("depends_on", []) for node, data in graph.items()})
            sorter.prepare()
            results: dict[str, Any] = {}
            readonly_view = OrchestratorReadonlyView(self.blackboard)
            active_tasks: list[asyncio.Task] = []

            try:
                while sorter.is_active():
                    ready = list(sorter.get_ready())
                    tasks = [
                        asyncio.create_task(self._execute_with_retry(graph[node], node, results, readonly_view))
                        for node in ready
                    ]
                    for task, node in zip(tasks, ready):
                        task.set_name(node)
                    active_tasks = tasks

                    node_results = await asyncio.gather(*tasks, return_exceptions=True)
                    active_tasks = []

                    abort_occurred = False
                    cancel_occurred = False
                    for node, result in zip(ready, node_results):
                        if isinstance(result, asyncio.CancelledError):
                            cancel_occurred = True
                            logger.error(f"DAG node '{node}' was cancelled")
                            results[node] = MISSING
                        elif isinstance(result, AbortExecutionException):
                            abort_occurred = True
                            logger.error(f"DAG abort signal from node '{node}': {result}")
                        elif isinstance(result, BaseException):
                            logger.error(f"Unhandled exception in node '{node}': {result}")
                            results[node] = MISSING
                        else:
                            results[node] = result
                        sorter.done(node)

                    if cancel_occurred or abort_occurred:
                        for t in tasks:
                            if not t.done():
                                t.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        if cancel_occurred:
                            raise asyncio.CancelledError("DAG execution cancelled due to node cancellation")
                        else:
                            raise AbortExecutionException("DAG execution aborted due to node failure")

                return results
            finally:
                if active_tasks:
                    for t in active_tasks:
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(*active_tasks, return_exceptions=True)
        except Exception:
            if self.metrics:
                self.metrics.update_counter("workflows_failed")
            raise
        else:
            elapsed = time.monotonic() - start_time
            if self.metrics:
                self.metrics.update_counter("workflows_completed")
                self.metrics.observe_histogram("workflow_duration_seconds", elapsed)
            if self.logger:
                self.logger.info("DAG execution completed", duration=elapsed)

    async def _execute_with_retry(self, node: dict, node_name: str, all_results: dict, view: OrchestratorReadonlyView):
        task_fn = node["task"]
        if not asyncio.iscoroutinefunction(task_fn):
            raise TypeError(f"Task '{node_name}' must be an async function accepting (deps, blackboard).")
        deps = {d: all_results.get(d, MISSING) for d in node.get("depends_on", [])}
        max_attempts = node.get("retry_policy", {}).get("max_attempts", 1)
        backoff_type = node.get("retry_policy", {}).get("backoff_type", "constant")
        base = node.get("retry_policy", {}).get("backoff_base", 1.0)
        max_backoff = node.get("retry_policy", {}).get("max_backoff", 30.0)

        if self.logger:
            self.logger.debug("Executing node", node=node_name, max_attempts=max_attempts)

        for attempt in range(max_attempts):
            node_start = time.monotonic()
            try:
                if self.hitl_manager:
                    await _run_hitl_gate(self.hitl_manager, self.workflow_id, node_name, node, deps, all_results)
                if self.checkpoint_manager:
                    await _save_node_checkpoint(
                        self.checkpoint_manager,
                        self.workflow_id,
                        node_name,
                        node,
                        deps,
                        all_results,
                        phase="before",
                    )

                result = await task_fn(deps, view)

                if self.checkpoint_manager:
                    await _save_node_checkpoint(
                        self.checkpoint_manager,
                        self.workflow_id,
                        node_name,
                        node,
                        deps,
                        all_results,
                        result=result,
                        phase="after",
                    )
                elapsed = time.monotonic() - node_start
                if self.metrics:
                    self.metrics.update_counter("tasks_completed")
                    self.metrics.observe_histogram("task_duration_seconds", elapsed)
                if self.logger:
                    self.logger.debug("Node completed", node=node_name, attempt=attempt + 1, duration=elapsed)
                return result
            except asyncio.CancelledError:
                raise
            except AbortExecutionException:
                raise
            except Exception as e:
                elapsed = time.monotonic() - node_start
                if self.metrics:
                    if attempt == max_attempts - 1:
                        self.metrics.update_counter("tasks_failed", labels={"error_type": type(e).__name__})
                    else:
                        self.metrics.update_counter("tasks_retried")
                if attempt == max_attempts - 1:
                    on_failure = node.get("on_failure", "abort")
                    if callable(on_failure):
                        action = on_failure(e, node_name, deps)
                        if action is MISSING:
                            return MISSING
                        raise
                    elif on_failure == "skip":
                        if self.logger:
                            self.logger.warning("Node skipped after failure", node=node_name, error=str(e))
                        return MISSING
                    else:
                        raise AbortExecutionException(f"Node '{node_name}' aborted: {e}")
                if self.logger:
                    self.logger.warning("Node failed, retrying", node=node_name, attempt=attempt + 1, error=str(e))
                delay = base if backoff_type == "constant" else min(base * (2**attempt), max_backoff)
                await asyncio.sleep(delay)
        return MISSING


class DynamicOrchestrator:
    def __init__(
        self,
        blackboard: SecureBlackboard,
        hitl_manager: Optional["HITLManager"] = None,
        checkpoint_manager: Optional["CheckpointManager"] = None,
        workflow_id: str | None = None,
    ):
        self.blackboard = blackboard
        self.hitl_manager = hitl_manager
        self.checkpoint_manager = checkpoint_manager
        self.workflow_id = workflow_id or "default"

    async def execute(self, initial_graph: TaskGraph, global_timeout: float | None = None) -> dict[str, Any]:
        graph = dict(initial_graph)
        results: dict[str, Any] = {}
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {node: [] for node in graph}

        for node, info in graph.items():
            deps = info.get("depends_on", [])
            in_degree[node] = len(deps)
            for dep in deps:
                dependents.setdefault(dep, []).append(node)

        ready_queue: asyncio.Queue[str] = asyncio.Queue()
        for node, deg in in_degree.items():
            if deg == 0:
                ready_queue.put_nowait(node)

        completed: set[str] = set()
        active_tasks: set[asyncio.Task] = set()
        readonly_view = OrchestratorReadonlyView(self.blackboard)

        deadline = time.monotonic() + global_timeout if global_timeout else None

        async def cancel_all_active():
            if not active_tasks:
                return
            for t in active_tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*active_tasks, return_exceptions=True)

        try:
            while len(completed) < len(graph):
                if deadline and time.monotonic() > deadline:
                    await cancel_all_active()
                    raise TimeoutError(f"DynamicOrchestrator global timeout after {global_timeout}s")

                ready = []
                while not ready_queue.empty():
                    ready.append(ready_queue.get_nowait())

                if not ready:
                    if len(completed) == len(graph):
                        break
                    if not active_tasks:
                        logger.critical("Deadlock: %s", set(graph.keys()) - completed)
                        raise RuntimeError("Deadlock")
                    if deadline:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            await cancel_all_active()
                            raise TimeoutError(f"DynamicOrchestrator global timeout after {global_timeout}s")
                        done, _ = await asyncio.wait_for(
                            asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED), timeout=remaining
                        )
                    else:
                        done, _ = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        active_tasks.discard(task)
                        self._handle_completed(task, graph, results, completed, dependents, in_degree, ready_queue)
                    continue

                tasks = []
                for name in ready:
                    task = asyncio.create_task(self._execute_with_retry(graph[name], name, results, readonly_view))
                    task.set_name(name)
                    tasks.append(task)
                    active_tasks.add(task)

                if tasks:
                    if deadline:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            await cancel_all_active()
                            raise TimeoutError(f"DynamicOrchestrator global timeout after {global_timeout}s")
                        done, _ = await asyncio.wait_for(
                            asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED), timeout=remaining
                        )
                    else:
                        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        active_tasks.discard(task)
                        self._handle_completed(task, graph, results, completed, dependents, in_degree, ready_queue)

            return results

        except AbortExecutionException:
            await cancel_all_active()
            raise
        except asyncio.CancelledError:
            await cancel_all_active()
            raise
        except Exception:
            await cancel_all_active()
            raise
        finally:
            # 最终保障：任何退出路径下清理残留活跃任务
            if active_tasks:
                for t in active_tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*active_tasks, return_exceptions=True)

    def _handle_completed(self, task: asyncio.Task, graph, results, completed, dependents, in_degree, ready_queue):
        name = task.get_name()
        if task.cancelled() or (task.exception() and isinstance(task.exception(), asyncio.CancelledError)):
            raise AbortExecutionException(f"Node '{name}' was cancelled")

        if task.exception():
            res = task.exception()
        else:
            res = task.result()

        if isinstance(res, AbortExecutionException):
            raise res

        if isinstance(res, BaseException):
            logger.error(f"Node '{name}' failed: {res}")
            results[name] = MISSING
        else:
            results[name] = res
        completed.add(name)

        node_def = graph[name]
        if node_def.get("dynamic") and isinstance(results[name], dict) and "subgraph" in results[name]:
            subgraph = results[name]["subgraph"]
            for sub_name, sub_node in subgraph.items():
                new_name = f"{name}::{sub_name}"
                new_node = dict(sub_node)
                raw_deps = new_node.get("depends_on", [])
                new_deps = []
                seen = set()
                for d in raw_deps:
                    if d not in seen:
                        seen.add(d)
                        new_deps.append(d)
                if name not in seen:
                    new_deps.append(name)
                new_node["depends_on"] = new_deps
                graph[new_name] = new_node
                unmet = sum(1 for d in new_deps if d not in completed)
                in_degree[new_name] = unmet
                for dep in new_deps:
                    dependents.setdefault(dep, []).append(new_name)
                if unmet == 0:
                    ready_queue.put_nowait(new_name)

        for successor in dependents.get(name, []):
            if successor not in completed:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    ready_queue.put_nowait(successor)

    async def _execute_with_retry(self, node: dict, node_name: str, all_results: dict, view: OrchestratorReadonlyView):
        task_fn = node["task"]
        if not asyncio.iscoroutinefunction(task_fn):
            raise TypeError(f"Task '{node_name}' must be an async function (deps, blackboard)")
        deps = {d: all_results.get(d, MISSING) for d in node.get("depends_on", [])}
        max_attempts = node.get("retry_policy", {}).get("max_attempts", 1)
        backoff_type = node.get("retry_policy", {}).get("backoff_type", "constant")
        base = node.get("retry_policy", {}).get("backoff_base", 1.0)
        max_backoff = node.get("retry_policy", {}).get("max_backoff", 30.0)

        for attempt in range(max_attempts):
            try:
                if self.hitl_manager:
                    await _run_hitl_gate(self.hitl_manager, self.workflow_id, node_name, node, deps, all_results)
                if self.checkpoint_manager:
                    await _save_node_checkpoint(
                        self.checkpoint_manager,
                        self.workflow_id,
                        node_name,
                        node,
                        deps,
                        all_results,
                        phase="before",
                    )

                result = await task_fn(deps, view)

                if self.checkpoint_manager:
                    await _save_node_checkpoint(
                        self.checkpoint_manager,
                        self.workflow_id,
                        node_name,
                        node,
                        deps,
                        all_results,
                        result=result,
                        phase="after",
                    )
                return result
            except asyncio.CancelledError:
                raise
            except AbortExecutionException:
                raise
            except Exception as e:
                if attempt == max_attempts - 1:
                    on_failure = node.get("on_failure", "abort")
                    if callable(on_failure):
                        action = on_failure(e, node_name, deps)
                        if action is MISSING:
                            return MISSING
                        raise
                    elif on_failure == "skip":
                        return MISSING
                    else:
                        raise AbortExecutionException(f"Node '{node_name}' aborted: {e}")
                delay = base if backoff_type == "constant" else min(base * (2**attempt), max_backoff)
                await asyncio.sleep(delay)
        return MISSING
