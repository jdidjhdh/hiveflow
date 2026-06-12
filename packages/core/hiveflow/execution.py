"""Pluggable execution backends for multi-agent TaskGraph plans.

HiveFlow Core schedules and coordinates multi-agent work through
:class:`~hiveflow.orchestrator.DynamicOrchestrator` by default
(:class:`NativeExecutionBackend`). External runtimes such as LangGraph can
integrate via the sidecar pattern (see docs cookbook ``langgraph-sidecar``) or
a future :class:`LangGraphExecutionBackend` runtime bridge.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from . import TaskGraph
from .adapters.langgraph import LangGraphSpec, taskgraph_to_langgraph
from .orchestrator import DynamicOrchestrator


@dataclass
class GraphExecutionResult:
    """Normalized result from any :class:`ExecutionBackend`."""

    backend: str
    results: dict[str, Any]
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionBackendNotReadyError(NotImplementedError):
    """Raised when a backend is registered but runtime execution is not available yet."""


class ExecutionBackend(ABC):
    """Execute a HiveFlow TaskGraph using a specific runtime."""

    name: str

    @abstractmethod
    async def execute(
        self,
        graph: TaskGraph,
        *,
        global_timeout: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> GraphExecutionResult:
        """Run *graph* and return node outputs keyed by node id."""


class NativeExecutionBackend(ExecutionBackend):
    """Default backend — HiveFlow :class:`~hiveflow.orchestrator.DynamicOrchestrator`."""

    name = "native"

    def __init__(self, orchestrator: DynamicOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def execute(
        self,
        graph: TaskGraph,
        *,
        global_timeout: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> GraphExecutionResult:
        results = await self._orchestrator.execute(graph, global_timeout=global_timeout)
        meta: dict[str, Any] = {}
        if context:
            meta["context"] = context
        return GraphExecutionResult(backend=self.name, results=results, status="completed", metadata=meta)


class LangGraphExecutionBackend(ExecutionBackend):
    """LangGraph runtime bridge (**stub**, v0.3 preview).

    Use :meth:`to_langgraph_spec` for sidecar export today. :meth:`execute` will
    delegate to LangGraph when the bridge ships; until then it raises
    :class:`ExecutionBackendNotReadyError` with sidecar guidance.
    """

    name = "langgraph"

    @staticmethod
    def is_runtime_available() -> bool:
        try:
            import langgraph  # noqa: F401

            return True
        except ImportError:
            return False

    def to_langgraph_spec(
        self,
        plan: TaskGraph,
        *,
        workflow_id: str = "hiveflow_sidecar",
        interrupt_before: list[str] | None = None,
    ) -> LangGraphSpec:
        """Export a skill plan to LangGraph-oriented JSON for external execution."""
        return taskgraph_to_langgraph(
            plan,
            workflow_id=workflow_id,
            interrupt_before=interrupt_before,
        )

    async def execute(
        self,
        graph: TaskGraph,
        *,
        global_timeout: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> GraphExecutionResult:
        raise ExecutionBackendNotReadyError(
            "LangGraph runtime execution is not enabled in hiveflow 0.1.x. "
            "Use the sidecar pattern: export with LangGraphExecutionBackend.to_langgraph_spec(), "
            "run your graph in LangGraph, and wire HITL/audit through HiveFlow Studio "
            "(see docs/en/cookbook/langgraph-sidecar.md). "
            f"langgraph package installed: {self.is_runtime_available()}"
        )


def get_execution_backend(
    name: str,
    *,
    orchestrator: DynamicOrchestrator | None = None,
) -> ExecutionBackend:
    """Factory for registered backends."""
    key = name.strip().lower()
    if key == "native":
        if orchestrator is None:
            raise ValueError("orchestrator is required for native backend")
        return NativeExecutionBackend(orchestrator)
    if key == "langgraph":
        return LangGraphExecutionBackend()
    raise ValueError(f"Unknown execution backend: {name!r}. Supported: native, langgraph")
