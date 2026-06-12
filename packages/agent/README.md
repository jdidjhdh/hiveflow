# HiveFlow Agent Runtime

[English](README.md) · **简体中文**

**PyPI：** [`hiveflow-agent`](https://pypi.org/project/hiveflow-agent/) · **路径：** `packages/agent` · **依赖：** `hiveflow>=0.1`

The cognitive runtime layer. Agent sits on [Core](../core/README.md) and adds natural-language intent parsing, dynamic TaskGraph planning, ReAct workers, memory, guardrails, and MCP skill registration — exposed primarily through `HiveMindApp`.

## What it does

| Area | Components |
|------|------------|
| **Entry point** | `HiveMindApp` / `HiveMindConfig` — wires Core, LLM, memory, orchestrator |
| **Planning** | `CognitiveOrchestrator` — LLM-generated TaskGraph with replan on failure |
| **Execution** | Skill bindings → ReAct workers; schedules ECM tasks via Core scheduler |
| **Memory** | Short-term context + long-term vector recall |
| **Safety** | Input guard, output validator (optional) |
| **MCP** | Register plugin tools as Skills (`mcp_*`) |
| **HITL** | Optional plan approval gate (`enable_plan_hitl`) before graph execution |

## Key APIs

| Method | Purpose |
|--------|---------|
| `run_query(user_input)` | Parse intent → plan → (optional HITL) → execute → answer |
| `plan_only(user_input)` | Return TaskGraph JSON only, no execution |
| `execute_plan(graph_spec, query)` | Run a pre-built plan (e.g. from Studio canvas or LangGraph import) |

Studio exposes the same surface as HTTP: `/api/agent/query`, `/api/agent/plan-only`, `/api/agent/execute-plan`.

## When to use Agent

- Users describe tasks in natural language instead of hand-written DAGs
- You want automatic Skill graph generation and replanning
- Integrate with Studio Agent mode or call `HiveMindApp` from your own FastAPI/CLI app
- You already use Core and need a higher-level orchestration façade

For low-level ECM/scheduling only, use [Core](../core/README.md) alone. For visual HITL and analytics, add [Studio](../studio/README.md).

## Installation

```bash
pip install hiveflow-agent
```

From source (monorepo):

```bash
cd packages/agent
pip install -r requirements.txt   # includes editable ../core
pip install pytest pytest-asyncio pytest-timeout
```

## Quick Start

```python
import asyncio
from hiveflow import HiveFlowConfig, MockLLMClient
from app import HiveMindApp, HiveMindConfig
from memory.vector_store import InMemoryVectorStore


async def main():
    llm = MockLLMClient(response='{"research":{"task":"search","depends_on":[]},"final_answer":{"task":"summarize","depends_on":["research"]}}')
    config = HiveMindConfig(
        hiveflow_config=HiveFlowConfig(),
        llm=llm,
        embedding_llm=llm,
        vector_store=InMemoryVectorStore(),
        skill_registry={"search": "searcher", "summarize": "writer"},
    )
    app = HiveMindApp(config)
    await app.start()
    try:
        result = await app.run_query("Summarize latest AI news")
        print(result)
    finally:
        await app.shutdown()


asyncio.run(main())
```

See also: [`examples/08_cognitive_planning.py`](../../examples/08_cognitive_planning.py), [`examples/16_langgraph_export.py`](../../examples/16_langgraph_export.py).

## Environment variables (Studio / local)

| Variable | Effect |
|----------|--------|
| `HIVEFLOW_RUNTIME=agent` | Enable Agent mode in Studio backend |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | Mock LLM for CI / UI dev without API keys |
| `HIVEFLOW_PLAN_HITL=true` | Require human plan approval before execute |

## Development

```bash
cd packages/agent
pip install -e ".[dev]"   # or: pip install pytest-cov …
pytest tests/ \
  --ignore=tests/test_real_llm.py \
  --ignore=tests/test_llm_connection.py \
  --cov --cov-fail-under=60
```

### Optional: real LLM integration tests

Excluded from CI (non-deterministic; requires API keys or local Ollama):

```bash
export LLM_PROVIDER=deepseek   # or openai / anthropic / ollama
export DEEPSEEK_API_KEY=...
pytest tests/test_real_llm.py -v -m real_llm
```

**Release coupling:** publish `hiveflow-agent` and `hiveflow` from the **same git tag** (`v0.1.0` → both `0.1.0`). See [Quality Gates](https://hiveflow.github.io/hiveflow/en/quality-gates/).

## Documentation

- [Studio Agent cookbook](https://hiveflow.github.io/hiveflow/cookbook/studio-agent-mode/)
- [Studio Agent ops](https://hiveflow.github.io/hiveflow/studio-agent-ops/)
- [Architecture — Layer 2](https://hiveflow.github.io/hiveflow/architecture/)
- [Main repository README](../../README.md)

## License

MIT — same as the HiveFlow project root.
