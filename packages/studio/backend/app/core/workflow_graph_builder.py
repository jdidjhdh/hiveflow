"""Build HiveFlow TaskGraph from Studio ReactFlow workflow definitions."""
from __future__ import annotations

from typing import Any, Callable


def depends_on_from_edges(edges: list[dict], node_ids: set[str]) -> dict[str, list[str]]:
    """Map target node -> list of source node ids from ReactFlow edges."""
    deps: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for edge in edges or []:
        source = edge.get("source")
        target = edge.get("target")
        if not target or target not in deps:
            continue
        if source and source not in deps[target]:
            deps[target].append(source)
    return deps


def normalize_studio_node(node: dict) -> dict:
    """Extract task spec fields from ReactFlow node or legacy flat node."""
    data = node.get("data") or {}
    return {
        "id": node.get("id"),
        "task": data.get("task") or node.get("task") or node.get("id"),
        "variant": data.get("variant") or node.get("variant", "task"),
        "depends_on": node.get("depends_on") or data.get("depends_on") or [],
        "on_failure": data.get("on_failure") or node.get("on_failure", "abort"),
        "retry_policy": data.get("retry_policy") or node.get("retry_policy") or {},
        "dynamic": data.get("dynamic") or node.get("dynamic", False),
        "hitl_config": data.get("hitl_config") or node.get("hitl_config") or {},
        "code": data.get("code") or node.get("code") or "",
        "config": data.get("config") or node.get("config") or {},
        "type": node.get("type", "taskNode"),
    }


def build_taskgraph_from_workflow(
    nodes: list[dict],
    edges: list[dict],
    task_factory: Callable[[dict], Any],
) -> dict:
    """Build TaskGraph dict from saved workflow nodes + edges."""
    normalized = [normalize_studio_node(n) for n in nodes if n.get("id")]
    node_ids = {n["id"] for n in normalized if n.get("id")}
    edge_deps = depends_on_from_edges(edges, node_ids)

    graph: dict = {}
    for node in normalized:
        node_id = node["id"]
        if not node_id:
            continue
        explicit_deps = node.get("depends_on") or []
        depends_on = explicit_deps if explicit_deps else edge_deps.get(node_id, [])
        graph[node_id] = {
            "task": task_factory(node),
            "depends_on": depends_on,
            "on_failure": node.get("on_failure", "abort"),
            "retry_policy": node.get("retry_policy") or {},
            "dynamic": node.get("dynamic", False),
            "variant": node.get("variant", "task"),
            "hitl_config": node.get("hitl_config") or {},
        }
    return graph
