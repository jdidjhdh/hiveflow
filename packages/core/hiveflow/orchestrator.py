from graphlib import TopologicalSorter
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set

try:
    from . import MISSING, TaskGraph, AbortExecutionException
    from .blackboard import SecureBlackboard, OrchestratorReadonlyView
except ImportError:
    from hiveflow import MISSING, TaskGraph, AbortExecutionException
    from blackboard import SecureBlackboard, OrchestratorReadonlyView

logger = logging.getLogger(__name__)


class DAGOrchestrator:
    def __init__(self, blackboard: SecureBlackboard, metrics=None, logger=None, tracer=None):
        self.blackboard = blackboard
        self.metrics = metrics
        self.logger = logger
        self.tracer = tracer

    async def execute(self, graph: TaskGraph) -> Dict[str, Any]:
        start_time = time.monotonic()
        if self.logger:
            self.logger.info("DAG execution started", node_count=len(graph))
        if self.metrics:
            self.metrics.update_counter("workflows_total")

        try:
            sorter = TopologicalSorter({node: data.get("depends_on", []) for node, data in graph.items()})
            sorter.prepare()
            results: Dict[str, Any] = {}
            readonly_view = OrchestratorReadonlyView(self.blackboard)
            active_tasks: List[asyncio.Task] = []

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
                result = await task_fn(deps, view)
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
                delay = base if backoff_type == "constant" else min(base * (2 ** attempt), max_backoff)
                await asyncio.sleep(delay)
        return MISSING


class DynamicOrchestrator:
    def __init__(self, blackboard: SecureBlackboard):
        self.blackboard = blackboard

    async def execute(self, initial_graph: TaskGraph, global_timeout: Optional[float] = None) -> Dict[str, Any]:
        graph = dict(initial_graph)
        results: Dict[str, Any] = {}
        in_degree: Dict[str, int] = {}
        dependents: Dict[str, List[str]] = {node: [] for node in graph}

        for node, info in graph.items():
            deps = info.get("depends_on", [])
            in_degree[node] = len(deps)
            for dep in deps:
                dependents.setdefault(dep, []).append(node)

        ready_queue = asyncio.Queue()
        for node, deg in in_degree.items():
            if deg == 0:
                ready_queue.put_nowait(node)

        completed: Set[str] = set()
        active_tasks: Set[asyncio.Task] = set()
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
                            asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED),
                            timeout=remaining
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
                            asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED),
                            timeout=remaining
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
                return await task_fn(deps, view)
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
                delay = base if backoff_type == "constant" else min(base * (2 ** attempt), max_backoff)
                await asyncio.sleep(delay)
        return MISSING