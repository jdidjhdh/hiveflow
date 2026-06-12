"""LangGraph interoperability (PoC).

Converts between HiveFlow TaskGraph plans (skill-based JSON from plan-only / cognitive
orchestrator) and a serializable LangGraph-oriented spec. Does **not** require
``langgraph`` to be installed — use :func:`render_langgraph_python` for optional codegen.

Status: **experimental / v0.3 preview**. Round-trip may lose HITL/checkpoint metadata.
"""

from __future__ import annotations

import json
from typing import Any

TaskGraphPlan = dict[str, dict[str, Any]]
LangGraphSpec = dict[str, Any]

SPEC_VERSION = "0.1-poc"


def taskgraph_to_langgraph(
    plan: TaskGraphPlan,
    *,
    workflow_id: str = "hiveflow_export",
    interrupt_before: list[str] | None = None,
) -> LangGraphSpec:
    """Export a HiveFlow TaskGraph plan to a LangGraph-oriented JSON spec.

    Args:
        plan: Skill plan, e.g. ``{"research": {"task": "search", "depends_on": []}, ...}``.
        workflow_id: Identifier embedded in metadata.
        interrupt_before: Node ids that map to LangGraph ``interrupt_before`` (HITL hint).

    Returns:
        JSON-serializable dict with ``nodes``, ``edges``, ``entry_point``, ``interrupt_before``.
    """
    if not plan:
        raise ValueError("plan must not be empty")

    node_ids = list(plan.keys())
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    incoming: dict[str, set[str]] = {n: set() for n in node_ids}
    for name, data in plan.items():
        for dep in data.get("depends_on") or []:
            if dep not in plan:
                raise ValueError(f"Unknown dependency '{dep}' for node '{name}'")
            incoming[name].add(dep)
            edges.append({"from": dep, "to": name})

    roots = [n for n in node_ids if not incoming[n]]
    if not roots:
        raise ValueError("plan has no entry nodes (cycle or empty depends_on)")
    entry_point = roots[0]

    leaves = [n for n in node_ids if not any(e["from"] == n for e in edges)]
    terminal = leaves[0] if len(leaves) == 1 else (leaves[-1] if leaves else node_ids[-1])

    for name, data in plan.items():
        meta = {k: v for k, v in data.items() if k not in ("task", "depends_on")}
        nodes.append(
            {
                "id": name,
                "action": data.get("task", name),
                "metadata": meta,
            }
        )

    edges.insert(0, {"from": "__start__", "to": entry_point})
    edges.append({"from": terminal, "to": "__end__"})

    hitl_nodes = interrupt_before or []
    for name, data in plan.items():
        if data.get("hitl") and name not in hitl_nodes:
            hitl_nodes.append(name)

    return {
        "version": SPEC_VERSION,
        "workflow_id": workflow_id,
        "state_schema": {
            "messages": "list",
            "results": "dict[str, Any]",
            "intent_id": "str",
        },
        "nodes": nodes,
        "edges": edges,
        "entry_point": entry_point,
        "interrupt_before": hitl_nodes,
        "source": "hiveflow",
    }


def langgraph_to_taskgraph(spec: LangGraphSpec) -> TaskGraphPlan:
    """Import a LangGraph-oriented JSON spec into a HiveFlow TaskGraph plan.

    Ignores ``__start__`` / ``__end__`` pseudo-nodes. Node ``action`` becomes ``task``.
    """
    if not spec.get("nodes"):
        raise ValueError("spec.nodes is required")

    plan: TaskGraphPlan = {}

    for node in spec["nodes"]:
        nid = node["id"]
        if nid in ("__start__", "__end__"):
            continue
        entry: dict[str, Any] = {
            "task": node.get("action") or node.get("task") or nid,
            "depends_on": [],
        }
        meta = dict(node.get("metadata") or {})
        if spec.get("interrupt_before") and nid in spec["interrupt_before"]:
            meta.setdefault("hitl", {"action": "approval", "prompt": f"Approve node '{nid}'?"})
        entry.update({k: v for k, v in meta.items() if k not in entry})
        plan[nid] = entry

    for edge in spec.get("edges") or []:
        src, dst = edge.get("from"), edge.get("to")
        if not src or not dst or src in ("__start__", "__end__") or dst in ("__start__", "__end__"):
            continue
        if dst not in plan:
            continue
        deps = plan[dst].setdefault("depends_on", [])
        if src in plan and src not in deps:
            deps.append(src)

    for name in list(plan.keys()):
        if not plan[name].get("depends_on"):
            plan[name]["depends_on"] = []

    if not plan:
        raise ValueError("no TaskGraph nodes parsed from spec")

    return plan


def render_langgraph_python(spec: LangGraphSpec, graph_name: str = "hiveflow_graph") -> str:
    """Generate illustrative LangGraph ``StateGraph`` Python source (requires ``langgraph`` at runtime)."""
    nodes = spec.get("nodes") or []
    edges = spec.get("edges") or []
    interrupt = spec.get("interrupt_before") or []

    lines = [
        '"""Auto-generated from HiveFlow LangGraph spec (PoC). Requires: pip install langgraph langchain-core"""',
        "from typing import Annotated, TypedDict",
        "from langgraph.graph import StateGraph, START, END",
        "",
        "",
        "class State(TypedDict):",
        "    messages: list",
        "    results: dict",
        "",
    ]

    for node in nodes:
        nid = node["id"]
        action = node.get("action", nid)
        fn = f"node_{nid.replace('-', '_')}"
        lines.extend(
            [
                f"async def {fn}(state: State) -> State:",
                f'    """HiveFlow skill: {action}"""',
                f"    state.setdefault('results', {{}})['{nid}'] = {{'skill': '{action}'}}",
                "    return state",
                "",
            ]
        )

    lines.append("builder = StateGraph(State)")
    for node in nodes:
        nid = node["id"]
        fn = f"node_{nid.replace('-', '_')}"
        lines.append(f'builder.add_node("{nid}", {fn})')

    for edge in edges:
        src, dst = edge.get("from"), edge.get("to")
        if src == "__start__":
            lines.append(f'builder.add_edge(START, "{dst}")')
        elif dst == "__end__":
            lines.append(f'builder.add_edge("{src}", END)')
        else:
            lines.append(f'builder.add_edge("{src}", "{dst}")')

    lines.append(f"{graph_name} = builder.compile()")
    if interrupt:
        lines.append(f"# HITL: configure interrupt_before={interrupt!r} when compiling with checkpointer")
    return "\n".join(lines) + "\n"


def dumps_langgraph_spec(spec: LangGraphSpec, *, indent: int = 2) -> str:
    """Pretty-print spec as JSON."""
    return json.dumps(spec, indent=indent, ensure_ascii=False)
