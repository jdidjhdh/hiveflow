import asyncio
import logging
import time
from collections import OrderedDict
from graphlib import TopologicalSorter, CycleError
from typing import TYPE_CHECKING, Any, Callable, Optional

from . import MISSING, AbortExecutionException, TaskGraph
from .blackboard import OrchestratorReadonlyView, SecureBlackboard
from .hitl import HITLAction, HITLStatus
from .observability.failure_reason import FailureReason

if TYPE_CHECKING:
    from .checkpoint import CheckpointManager
    from .hitl import HITLManager

logger = logging.getLogger(__name__)


class CycleDependencyError(Exception):
    """
    循环依赖错误

    当动态编排添加子图时检测到循环依赖时抛出。
    包含循环路径的详细信息。
    """

    def __init__(self, message: str, cycle_path: list[str] | None = None):
        super().__init__(message)
        self.cycle_path = cycle_path or []

    def __str__(self) -> str:
        if self.cycle_path:
            path_str = " -> ".join(self.cycle_path)
            return f"{super().__str__()} Cycle path: {path_str}"
        return super().__str__()


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
        reason = (
            FailureReason.HITL_REJECTED.value if gate.status == HITLStatus.REJECTED else FailureReason.TIMEOUT.value
        )
        raise AbortExecutionException(
            f"HITL gate rejected or timed out for node '{node_name}' ({gate.status.value})",
            failure_reason=reason,
        )
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
        # 🔄 P0 FIX: Track internal state for reset capability
        self._executed_nodes: set[str] = set()  # Nodes that have been executed
        self._pending_dependencies: dict[str, set[str]] = {}  # Pending deps for each node
        # 🔄 Transaction Compensation: Registry for compensation handlers
        self._compensation_handlers: OrderedDict[str, Callable] = OrderedDict()  # node_id -> compensation handler

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

                # 🔄 Transaction Compensation: Register compensation handler on success
                compensate_fn = node.get("compensate")
                if compensate_fn is not None:
                    if asyncio.iscoroutinefunction(compensate_fn):
                        self.register_compensation(node_name, compensate_fn)
                    else:
                        # Wrap sync function in async wrapper
                        async def async_compensate_wrapper(node_id=node_name, fn=compensate_fn):
                            return fn()
                        self.register_compensation(node_name, async_compensate_wrapper)

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
                    # 🔄 Transaction Compensation: Execute compensations when node fails
                    await self.execute_compensations(node_name)
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

    def register_compensation(self, node_id: str, handler: Callable) -> None:
        """
        Register a compensation handler for a node.

        Args:
            node_id: Identifier of the node
            handler: Async callable to execute for compensation
        """
        self._compensation_handlers[node_id] = handler
        logger.debug(f"Registered compensation handler for node '{node_id}'")

    async def execute_compensations(self, failed_node_id: str) -> None:
        """
        Execute all registered compensation handlers in reverse order.

        Called when a node fails to rollback previously successful nodes.

        Args:
            failed_node_id: ID of the node that failed
        """
        if not self._compensation_handlers:
            logger.info(f"No compensation handlers to execute for failed node '{failed_node_id}'")
            return

        logger.warning(
            f"Executing {len(self._compensation_handlers)} compensation(s) for failed node '{failed_node_id}'"
        )

        # Execute in reverse order (most recent first)
        for node_id in reversed(list(self._compensation_handlers.keys())):
            handler = self._compensation_handlers[node_id]
            try:
                logger.info(f"Executing compensation for node '{node_id}'")
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                logger.error(f"Compensation failed for node '{node_id}': {e}")

        # Clear handlers after execution
        self._compensation_handlers.clear()

    def reset(self) -> None:
        """
        🔄 P0 FIX: Reset the orchestrator internal state.

        Clears all tracked execution state (_executed_nodes, _pending_dependencies, _compensation_handlers),
        allowing the orchestrator to be reused for a new workflow without state leakage.

        This prevents unlimited growth of internal lists when orchestrator is reused
        across multiple workflow executions.

        Call this method between workflow runs or when starting a fresh execution.
        """
        self._executed_nodes.clear()
        self._pending_dependencies.clear()
        self._compensation_handlers.clear()
        logger.info(f"DynamicOrchestrator reset: cleared internal state for workflow_id={self.workflow_id}")

    def add_subgraph(
        self,
        parent_node: str,
        subgraph: TaskGraph,
        current_graph: TaskGraph,
        running_nodes: set[str] | None = None,
    ) -> TaskGraph:
        """
        🔧 循环依赖检测：添加子图前检测循环依赖

        Args:
            parent_node: 动态生成子图的父节点名称
            subgraph: 要添加的子图（TaskGraph）
            current_graph: 当前已有的图结构
            running_nodes: 当前正在运行的节点集合（用于检测是否引用正在运行的节点）

        Returns:
            合并后的完整图结构

        Raises:
            CycleDependencyError: 如果检测到循环依赖

        使用方式:
            orchestrator = DynamicOrchestrator(...)
            try:
                new_graph = orchestrator.add_subgraph(
                    parent_node="dynamic_node",
                    subgraph={"sub1": {...}, "sub2": {...}},
                    current_graph=current_graph,
                    running_nodes={"node_a", "node_b"}
                )
            except CycleDependencyError as e:
                logger.error(f"Cycle detected: {e}")
        """
        running_nodes = running_nodes or set()

        # 构建合并后的图结构
        merged_graph = dict(current_graph)

        # 处理子图节点名称和依赖关系
        for sub_name, sub_node in subgraph.items():
            new_name = f"{parent_node}::{sub_name}"
            new_node = dict(sub_node)

            # 处理依赖关系：引用同一子图内的节点转换为完整名称
            raw_deps = new_node.get("depends_on", [])
            new_deps = []
            seen = set()

            for d in raw_deps:
                if d not in seen:
                    seen.add(d)
                    # 如果依赖的是子图内的节点，转换为完整名称
                    if d in subgraph:
                        new_deps.append(f"{parent_node}::{d}")
                    else:
                        new_deps.append(d)

            # 确保依赖父节点（防止子图节点在没有父节点完成前执行）
            if parent_node not in seen:
                new_deps.append(parent_node)

            new_node["depends_on"] = new_deps
            merged_graph[new_name] = new_node

        # 🔧 检测循环依赖
        self._detect_cycle(merged_graph, parent_node, running_nodes)

        return merged_graph

    def _detect_cycle(
        self,
        graph: TaskGraph,
        parent_node: str,
        running_nodes: set[str],
    ) -> None:
        """
        检测图中的循环依赖

        Args:
            graph: 要检测的图结构
            parent_node: 父节点名称
            running_nodes: 当前正在运行的节点集合

        Raises:
            CycleDependencyError: 如果检测到循环依赖
        """
        # 构建依赖关系字典
        dependency_map: dict[str, list[str]] = {}
        for node_name, node_data in graph.items():
            deps = node_data.get("depends_on", [])
            dependency_map[node_name] = deps

        # 方法1：使用 TopologicalSorter 检测循环
        try:
            sorter = TopologicalSorter(dependency_map)
            sorter.prepare()
        except CycleError as e:
            # 拓扑排序检测到循环，提取循环路径
            cycle_path = self._find_cycle_path(dependency_map)
            raise CycleDependencyError(
                f"Cycle dependency detected in subgraph from node '{parent_node}'",
                cycle_path=cycle_path,
            )

        # 方法2：检测是否引用正在运行的节点（可能导致死循环）
        # 新添加的子图节点如果依赖正在运行的节点，而正在运行的节点又依赖新节点，会形成循环
        subgraph_nodes = set()
        for node_name in graph:
            if node_name.startswith(f"{parent_node}::"):
                subgraph_nodes.add(node_name)

        # 检查新子图节点是否被正在运行的节点依赖
        for running_node in running_nodes:
            if running_node not in graph:
                continue
            running_deps = graph[running_node].get("depends_on", [])
            for dep in running_deps:
                if dep in subgraph_nodes:
                    # 正在运行的节点依赖新添加的子图节点
                    # 这可能导致死循环（因为运行节点等待子图节点，子图节点等待父节点）
                    cycle_path = [running_node, dep, parent_node, running_node]
                    raise CycleDependencyError(
                        f"Running node '{running_node}' depends on new subgraph node '{dep}'. "
                        f"This creates a potential deadlock.",
                        cycle_path=cycle_path,
                    )

        # 方法3：检测父节点是否被子图节点间接依赖
        # 父节点已经完成或正在运行，如果子图节点依赖链回到父节点，会形成循环
        for sub_node in subgraph_nodes:
            path = self._trace_dependency_path(sub_node, parent_node, dependency_map)
            if path and parent_node in path and len(path) > 1:
                # 找到从子图节点回到父节点的路径
                cycle_path = path + [sub_node]
                raise CycleDependencyError(
                    f"Subgraph node '{sub_node}' creates a cycle back to parent '{parent_node}'",
                    cycle_path=cycle_path,
                )

    def _find_cycle_path(self, dependency_map: dict[str, list[str]]) -> list[str]:
        """
        在依赖图中找到循环路径

        使用 DFS 深度优先搜索检测循环并提取路径。

        Args:
            dependency_map: 节点依赖关系字典

        Returns:
            循环路径列表（如果找不到则返回空列表）
        """
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in dependency_map.get(node, []):
                if dep not in visited:
                    result = dfs(dep)
                    if result:
                        return result
                elif dep in rec_stack:
                    # 找到循环，提取循环部分
                    cycle_start_idx = path.index(dep)
                    return path[cycle_start_idx:] + [dep]

            path.pop()
            rec_stack.remove(node)
            return None

        # 从每个未访问的节点开始 DFS
        for node in dependency_map:
            if node not in visited:
                result = dfs(node)
                if result:
                    return result

        return []

    def _trace_dependency_path(
        self,
        start_node: str,
        target_node: str,
        dependency_map: dict[str, list[str]],
    ) -> list[str] | None:
        """
        追踪从 start_node 到 target_node 的依赖路径

        Args:
            start_node: 开始节点
            target_node: 目标节点
            dependency_map: 节点依赖关系字典

        Returns:
            路径列表（如果找不到则返回 None）
        """
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            visited.add(node)
            path.append(node)

            if node == target_node:
                return list(path)

            for dep in dependency_map.get(node, []):
                if dep not in visited:
                    result = dfs(dep)
                    if result:
                        return result

            path.pop()
            return None

        return dfs(start_node)
