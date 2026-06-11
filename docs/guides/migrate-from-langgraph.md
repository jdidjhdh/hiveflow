# Migrating from LangGraph

Concept mapping between LangGraph and HiveFlow. HiveFlow targets teams that need **HITL**, **Studio UI**, and **secure shared state** out of the box.

## Concept map

| LangGraph | HiveFlow | Notes |
|-----------|----------|-------|
| `StateGraph` | `DAGOrchestrator` / `CognitiveOrchestrator` | Static vs runtime-generated plans |
| Graph nodes | Agents + `task_handler` | Skills-based scheduling |
| Shared state | `SecureBlackboard` | Encrypted + audited keys |
| `interrupt()` / human node | `HITLManager` + `HITLAction` | Native gates + Studio Approvals |
| Checkpointer | `CheckpointManager` | Blackboard snapshots |
| Tool calling | MCP + `ReActWorker` | MCP-first plugin model |
| LangSmith traces | Studio Tracer / Replay | `trace_id` ↔ `intent_id` |

## Typical migration paths

### 1. Fixed DAG → Core orchestrator

Replace LangGraph edges with a HiveFlow task graph or Studio Orchestrator canvas, then execute via Core scheduler or `/api/workflows/execute`.

### 2. Dynamic agent → Agent runtime

Replace `create_react_agent` loops with:

```python
from app import HiveMindApp, HiveMindConfig  # hiveflow-agent

result = await app.run_query("Summarize the quarterly report")
```

Studio equivalent: `POST /api/agent/query`.

### 3. Human approval

LangGraph `interrupt_before` → HiveFlow:

```python
gate = await hitl.create_gate(
    workflow_id="wf-1",
    node_id="publish",
    action=HITLAction.APPROVAL,
    prompt="Approve before publish",
    context={"draft": "..."},
)
```

See [HITL Cookbook](../cookbook/hitl-approval.md).

## What is not 1:1 yet

- **LangGraph adapter** — PoC available: [LangGraph integration](../integrations/langgraph.md) (`taskgraph_to_langgraph` / round-trip). Full runtime bridge planned v0.3.
- **LangChain Tool wrappers** — use MCP or custom `ReActTool` today
- **LangSmith hosted eval** — use HiveFlow `Evaluator` + Studio Analytics

## Next steps

- [Getting Started](../getting-started.md)
- [Studio Agent Mode](../cookbook/studio-agent-mode.md)
