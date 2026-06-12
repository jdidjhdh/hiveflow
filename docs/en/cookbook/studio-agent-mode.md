# Studio Agent Mode

Run natural-language planning and DAG execution through HiveFlow Studio with the Agent runtime.

## When to use

- Visual orchestration with NL-generated plans (`plan-only`)
- Execute a plan graph step-by-step on the Agent runtime (`execute-plan`)
- Ad-hoc queries without building a workflow first (`query`)

## Prerequisites

```bash
# Backend (from repo root)
cd packages/studio/backend
pip install -r requirements.txt

export HIVEFLOW_RUNTIME=agent
export HIVEFLOW_AGENT_ECHO_LLM=true   # CI / local UI without API keys
export HIVEFLOW_PLAN_HITL=true        # optional: plan approval gate
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend
cd packages/studio/frontend
npm install && npm run dev
```

Open **Orchestrator**, enable **Agent / real mode**, then use the Agent drawer.

## Three HTTP APIs

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `POST /api/agent/query` | Full NL query → plan (+ HITL if enabled) → execute | `intent_id`, plan, results |
| `POST /api/agent/plan-only` | Generate plan JSON only (no execution) | `plan`, `intent_id` |
| `POST /api/agent/execute-plan` | Execute an existing plan graph | step results |

### plan-only → canvas → execute-plan

1. Call **plan-only** with your goal.
2. Click **导入到画布** in the Orchestrator drawer.
3. Click **执行 DAG** — in Agent mode this calls **execute-plan**, not Core `/api/workflows/execute`.

### Export to LangGraph

- **Agent drawer** (after plan-only / run_query): **导出 LangGraph JSON** or **导出 LangGraph + Python 模板**
- **Toolbar**: **导出 LangGraph** converts the current canvas TaskGraph via `POST /api/agent/export-langgraph`

### Chatflow

In Agent mode, **Chatflow** topologically sorts nodes and runs `ai_reply` steps via `run_query` per node (see `src/utils/chatflowTopology.ts`).

## Environment variables

| Variable | Effect |
|----------|--------|
| `HIVEFLOW_RUNTIME=agent` | Start with Agent runtime active |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | Mock LLM for plans (CI-friendly) |
| `HIVEFLOW_PLAN_HITL=true` | Pause for plan approval (`node_id=plan_approval`) |

## Troubleshooting

See [Studio Agent Operations](../studio-agent-ops.md).

## Related

- [HITL Approval](hitl-approval.md)
- [Getting Started](../getting-started.md#studio-agent-mode)
