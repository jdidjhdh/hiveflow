# LangGraph Integration (PoC)

**Status: experimental (v0.3 preview)** — converts HiveFlow TaskGraph plans to/from a LangGraph-oriented JSON spec. Does not execute LangGraph graphs inside HiveFlow.

## Install

```bash
pip install hiveflow
# Optional, to run generated code:
pip install langgraph langchain-core
```

## Export HiveFlow plan → LangGraph spec

After `plan-only` or cognitive planning, you receive a TaskGraph JSON:

```python
plan = {
    "research": {"task": "search", "depends_on": []},
    "draft": {"task": "write", "depends_on": ["research"]},
    "final_answer": {"task": "summarize", "depends_on": ["draft"]},
}
```

Convert:

```python
from hiveflow.adapters.langgraph import taskgraph_to_langgraph, dumps_langgraph_spec

spec = taskgraph_to_langgraph(plan, workflow_id="content_pipeline")
print(dumps_langgraph_spec(spec))
```

Output includes:

- `nodes[]` with `id` and `action` (HiveFlow skill name)
- `edges[]` including `__start__` / `__end__`
- `interrupt_before[]` — populated from nodes with `hitl` config

## Import LangGraph spec → HiveFlow plan

```python
from hiveflow.adapters.langgraph import langgraph_to_taskgraph

plan = langgraph_to_taskgraph(spec)
# Execute via POST /api/agent/execute-plan or CognitiveOrchestrator.execute_plan
```

## Generate LangGraph Python (illustrative)

```python
from hiveflow.adapters.langgraph import render_langgraph_python

code = render_langgraph_python(spec, graph_name="content_graph")
Path("exported_graph.py").write_text(code)
```

Generated code is a **starting point** — wire real tools and a checkpointer for production LangGraph HITL.

## Studio workflow

1. Orchestrator → Agent mode → **plan-only**
2. Export plan JSON from drawer (**导出 LangGraph JSON**) or API
3. `taskgraph_to_langgraph(plan)` → share with LangGraph team or run codegen
4. Round-trip: `langgraph_to_taskgraph(spec)` → **导入到画布** → **execute-plan**

Toolbar **导出 LangGraph** exports the current canvas graph without an Agent plan step.

## Limitations (PoC)

| Feature | Supported |
|---------|-----------|
| Skill topology / depends_on | ✅ |
| HITL → interrupt_before hint | ✅ |
| Checkpoint metadata | ❌ (lost on export) |
| Conditional edges | ❌ |
| Live LangGraph execution in Core | ❌ |
| LangChain Tool bridge | Planned |

## Tests

```bash
cd packages/core && pytest tests/test_langgraph_adapter.py -v
```

## See also

- [LangGraph + HiveFlow Sidecar cookbook](../cookbook/langgraph-sidecar.md) — run LangGraph externally, HITL/audit in HiveFlow
- [Migrate from LangGraph](../guides/migrate-from-langgraph.md)
- [Studio Agent Mode cookbook](../cookbook/studio-agent-mode.md)
