"""Execute persisted Studio workflows by id."""
from __future__ import annotations

import uuid

from app.core.engine_service import get_engine
from app.core.workflow_graph_builder import build_taskgraph_from_workflow
from app.api.workflows import _make_task_fn_from_node
from app.db.config import get_storage


async def execute_stored_workflow(workflow_id: str, wf_id: str | None = None) -> dict:
    storage = get_storage()
    if not storage:
        raise RuntimeError("Storage not initialized")

    workflow = await storage.get_workflow(workflow_id)
    if not workflow:
        raise ValueError(f"Workflow '{workflow_id}' not found")

    engine = get_engine()
    if not engine._running:
        raise RuntimeError("Engine not running")

    run_id = wf_id or f"wf_{uuid.uuid4().hex[:8]}"
    graph = build_taskgraph_from_workflow(
        workflow.nodes,
        workflow.edges,
        _make_task_fn_from_node,
    )
    if not graph:
        raise ValueError(f"Workflow '{workflow_id}' has no executable nodes")

    return await engine.execute_workflow(run_id, graph, mode="dag")
