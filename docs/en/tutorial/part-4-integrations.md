# Part 4 — Integrations

Multimodal processing and LangGraph interoperability.

## 4.1 Multimodal pipeline (Example 15)

Process images, audio, and video in a unified pipeline (mock providers in the example; swap for real APIs in production).

```bash
python examples/15_multimodal_pipeline.py
```

Typical outputs:

| Modality | Fields |
|----------|--------|
| Image | `description`, `labels`, `confidence` |
| Audio | `text` (transcript), `language` |
| Video | `summary`, `key_frames`, `scenes` |

Wire real providers by implementing the multimodal adapter interfaces in `hiveflow.multimodal`.

## 4.2 LangGraph export (Example 16)

Export a HiveFlow TaskGraph to LangGraph-compatible JSON and Python scaffold.

```bash
python examples/16_langgraph_export.py
```

The export includes:

- `state_schema` (messages, results, intent_id)
- `nodes` with actions/skills
- `edges` including `__start__` / `__end__`
- Optional `interrupt_before` for HITL nodes

Generated Python uses `langgraph` + `langchain-core` (PoC — see versioning policy).

### Sidecar pattern

Keep LangGraph as the **execution runtime** and HiveFlow as the **coordination layer** (HITL, audit, blackboard, Studio UI):

```
User → Studio → HiveFlow (HITL + audit + blackboard)
                      ↓
               LangGraph runtime (graph execution)
```

Deep dive: [LangGraph Sidecar cookbook](../cookbook/langgraph-sidecar.md) and [LangGraph integration](../integrations/langgraph.md).

### Studio export buttons

In **Orchestrator** (Agent mode):

1. **plan-only** → **Export LangGraph JSON** or **Export LangGraph + Python template**
2. Toolbar **Export LangGraph** — converts current canvas via `POST /api/agent/export-langgraph`

## 4.3 LLM provider integrations

| Provider | Doc | Env vars |
|----------|-----|----------|
| OpenAI | [integrations/openai.md](../integrations/openai.md) | `OPENAI_API_KEY` |
| Anthropic | [integrations/anthropic.md](../integrations/anthropic.md) | `ANTHROPIC_API_KEY` |
| Ollama | Agent `llm/ollama_client.py` | `OLLAMA_BASE_URL` |
| DeepSeek | Agent `llm/deepseek_client.py` | `DEEPSEEK_API_KEY` |

Route planning vs execution separately:

```bash
HIVEFLOW_LLM_PLANNING_PROVIDER=openai
HIVEFLOW_LLM_EXECUTION_PROVIDER=anthropic
```

## 4.4 MCP ecosystem

HiveFlow speaks MCP natively (`hiveflow.mcp`). Plugins register tools discoverable by any MCP-compatible agent. See [Part 2 — MCP](part-2-workflows.md#26-mcp-tools-example-07).

## 4.5 Exercises

1. Export Example 02's pipeline to LangGraph JSON and inspect node IDs.
2. Replace mock image analysis in Example 15 with a real vision API call.
3. Run LangGraph sidecar with `HIVEFLOW_PLAN_HITL=true` and approve a plan in Studio.

## Next

→ [Part 5 — Studio](part-5-studio.md): full visual ops UI walkthrough.
