# Part 2 — Workflows

Build multi-agent pipelines, add human approval, recover from failures, stream events, and connect RAG + MCP tools.

## 2.1 Multi-agent collaboration (Example 02)

Pattern: **research → write → review** via the blackboard.

```bash
python examples/02_multi_agent.py
```

Each agent:

1. Reads upstream keys from the blackboard (`view.get()`).
2. Processes the ECM payload.
3. Writes downstream keys (`view.put()`).

Scheduling order is explicit — you schedule ECM messages in sequence (or use a DAG orchestrator for automatic dependencies).

```python
# After research completes, schedule writer
await hf.scheduler.schedule(ECM(
    trace_id="pipeline-1",
    intent="Write article",
    intent_id="write-1",
    emitter="scheduler",
    required_skills=["write"],
    payload={"topic": "AI Trends 2025"},
))
```

**Design tip:** Keep blackboard keys stable and versioned (`article_draft_v2`) when HITL may edit intermediate results.

Deep dive: [Multi-agent debate cookbook](../cookbook/multi-agent-debate.md).

## 2.2 Human-in-the-Loop (Example 03)

Pause before irreversible actions (publish, send email, deploy).

```bash
python examples/03_hitl_approval.py
```

Core API:

```python
from hiveflow import HITLManager, HITLAction

hitl = HITLManager()
gate = await hitl.create_gate(
    workflow_id="content-pipeline",
    node_id="publish_review",
    action=HITLAction.APPROVAL,
    prompt="Approve publishing this draft?",
    context={"title": draft["title"], "body": draft["body"]},
)
# Workflow waits until:
await hitl.respond(gate.gate_id, approved=True, comment="LGTM")
```

In Studio, open **Approvals** to approve/reject gates. With `HIVEFLOW_PLAN_HITL=true`, plans are gated at `node_id=plan_approval` before execution.

Deep dive: [HITL approval cookbook](../cookbook/hitl-approval.md).

## 2.3 Checkpoints & time travel (Example 04)

Save workflow state snapshots and restore to a previous step.

```bash
python examples/04_checkpoint.py
```

Use cases:

- Retry failed steps without re-running expensive upstream work.
- Audit trail for regulated industries.
- Studio **Replay** page for post-mortems.

Deep dive: [Checkpoint recovery cookbook](../cookbook/checkpoint-recovery.md).

## 2.4 Streaming events (Example 05)

Emit typed SSE events for tokens, tool calls, and node lifecycle.

```bash
python examples/05_streaming.py
```

```python
from hiveflow import StreamBuffer, StreamEvent, StreamEventType, collect_stream

buffer = StreamBuffer()
await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="Hello"))
await buffer.put(StreamEvent(type=StreamEventType.DONE, data=None))
await buffer.close()
events = await collect_stream(buffer)
```

Wire `StreamBuffer` to FastAPI `StreamingResponse` for browser clients. Studio **Tracer** consumes WebSocket events with unified `intent_id` / `trace_id`.

## 2.5 RAG pipeline (Example 06)

Index documents, retrieve chunks, optionally generate answers.

```bash
python examples/06_rag_pipeline.py
```

Typical flow:

1. Create a knowledge base.
2. Index documents (title + body).
3. Query with natural language.
4. Retrieve ranked sources; plug in `llm_client` for generation.

Deep dive: [RAG + MCP cookbook](../cookbook/rag-mcp-pipeline.md).

## 2.6 MCP tools (Example 07)

Unified tool discovery and invocation via Model Context Protocol.

```bash
python examples/07_mcp_tools.py
```

Register tools, invoke by name, swap providers without changing agent code. Studio **Capability Market** surfaces installed MCP plugins.

## 2.7 Workflow patterns summary

| Pattern | When to use | Example |
|---------|-------------|---------|
| Sequential pipeline | Fixed steps, clear handoffs | `02_multi_agent.py` |
| HITL gate | Human approval before side effects | `03_hitl_approval.py` |
| Checkpoint | Fault tolerance, audit | `04_checkpoint.py` |
| Streaming | Chat UX, live progress | `05_streaming.py` |
| RAG + MCP | Knowledge + external tools | `06`, `07` |

## 2.8 Exercises

1. Add an HITL gate between writer and reviewer in Example 02.
2. Stream token events from a mock LLM handler in Example 05.
3. Index a local markdown file in Example 06 and query it.

## Next

→ [Part 3 — Advanced](part-3-advanced.md): cognitive planning, security, scaling, plugins.
