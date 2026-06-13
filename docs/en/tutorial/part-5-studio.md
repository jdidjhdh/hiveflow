# Part 5 — Studio

Complete walkthrough of HiveFlow Studio — the self-hosted ops UI.

## 5.1 Start Studio

### Docker (easiest)

```bash
docker compose up --build
```

| URL | Purpose |
|-----|---------|
| http://localhost:3000 | React frontend |
| http://localhost:8000 | FastAPI backend |
| http://localhost:8000/docs | OpenAPI Swagger |

### Local dev (two terminals)

```bash
# Terminal 1 — backend
cd packages/studio/backend
pip install -r requirements.txt
export HIVEFLOW_RUNTIME=agent
export HIVEFLOW_AGENT_ECHO_LLM=true
export HIVEFLOW_PLAN_HITL=true
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd packages/studio/frontend
npm install && npm run dev
```

## 5.2 Golden Path — Agent mode

1. Open **Orchestrator**.
2. Toggle **Agent / real mode** in the toolbar.
3. Enter a goal: *Summarize three trends in AI agents*.
4. Click **Plan only** — review the generated TaskGraph.
5. Click **Import to canvas**.
6. Click **Execute DAG**.

With `HIVEFLOW_PLAN_HITL=true`, step 4 creates a gate at **Approvals** before execution.

Deep dive: [Studio Agent Mode cookbook](../cookbook/studio-agent-mode.md).

## 5.3 Studio pages reference

| Page | Purpose |
|------|---------|
| **Dashboard** | System overview, recent activity |
| **Orchestrator** | DAG canvas, Agent drawer, plan/execute |
| **Chatflow** | Conversational flow builder; Agent mode runs `ai_reply` nodes via `run_query` |
| **Agents** | Register and configure agents |
| **Approvals** | HITL gates — approve/reject/edit plan JSON |
| **Blackboard** | Inspect shared keys in real time |
| **Analytics** | Execution metrics, success rates |
| **Tracer** | Live WebSocket trace (`intent_id`, `trace_id`) |
| **Replay** | Audit log + checkpoint replay by `intent_id` |
| **Events** | Event bus history |
| **Knowledge Base** | RAG document management |
| **LLM Config** | Provider keys and routing |
| **Capability Market** | MCP plugin install/uninstall |
| **Triggers** | Schedule and webhook triggers |
| **Variables** | Environment and workflow variables |
| **Prompt Templates** | Reusable prompt library |
| **A/B Testing** | Compare prompt/model variants |
| **Audit Log** | Compliance trail |
| **Settings** | Studio configuration |

## 5.4 Key HTTP APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/agent/query` | POST | NL query → plan → execute |
| `/api/agent/plan-only` | POST | Generate plan JSON only |
| `/api/agent/execute-plan` | POST | Execute existing plan graph |
| `/api/agent/export-langgraph` | POST | Export canvas to LangGraph |
| `/api/workflows/*` | * | Core DAG CRUD + execute |
| `/api/hitl/*` | * | Approval gates |
| `/api/blackboard/*` | * | Read/write shared state |
| `/api/analytics/*` | * | Metrics (real mode) |
| `/api/replay/*` | * | Checkpoint replay |

Full reference: [API Reference](../api-reference.md).

## 5.5 Environment variables

| Variable | Effect |
|----------|--------|
| `HIVEFLOW_RUNTIME=agent` | Default to Agent runtime |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | Mock LLM (no API key) |
| `HIVEFLOW_PLAN_HITL=true` | Plan approval before execute |
| `HIVEFLOW_LLM_PLANNING_PROVIDER` | Planning LLM route |
| `HIVEFLOW_LLM_EXECUTION_PROVIDER` | Execution LLM route |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Real LLM providers |

## 5.6 Chatflow vs Orchestrator

| Feature | Orchestrator | Chatflow |
|---------|--------------|----------|
| Layout | Free-form DAG canvas | Conversation-oriented graph |
| Best for | Batch pipelines, ETL, multi-step jobs | Chatbots, Q&A flows |
| Agent mode | plan-only → canvas → execute | Topological `ai_reply` nodes |

## 5.7 Troubleshooting Studio

| Symptom | Fix |
|---------|-----|
| Blank canvas after plan-only | Check browser console; verify `/api/agent/plan-only` 200 |
| Execute does nothing | Ensure **Agent / real mode** is on |
| No LLM response | Set `HIVEFLOW_AGENT_ECHO_LLM=true` or provide API keys |
| WS disconnect on Tracer | Confirm backend on :8000; check CORS / proxy |
| Approvals empty | Enable `HIVEFLOW_PLAN_HITL=true` and run plan-only first |

See [Studio Agent Operations](../studio-agent-ops.md).

## 5.8 Exercises

1. Complete Golden Path with a custom goal and export LangGraph JSON.
2. Reject a plan in **Approvals**, edit JSON, re-submit.
3. Open **Blackboard** during execution and watch keys update live.

## Next

→ [Part 6 — Production](part-6-production.md): deploy, monitor, maintain.
