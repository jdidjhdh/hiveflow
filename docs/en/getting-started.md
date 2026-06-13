# Getting Started with HiveFlow

This guide will help you get up and running with HiveFlow in minutes.

## Golden Path — Studio Agent mode

The fastest way to see HiveFlow: run Studio with Agent runtime, generate a plan from natural language, import it to the canvas, and execute.

### Docker (recommended)

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
docker compose up --build
```

Open **http://localhost:3000** → **Orchestrator** → enable **Agent / real mode** → **Plan only** → **Import to canvas** → **Execute DAG**.

See [Studio Agent cookbook](cookbook/studio-agent-mode.md) for API details and environment variables.

### PyPI quick check

```bash
pip install hiveflow-core hiveflow-agent
python examples/01_hello_hiveflow.py
```

---

## Prerequisites

- **Python 3.10+**
- **pip**
- **(Optional) Redis** — distributed blackboard and event bus
- **(Optional) Node.js 18+** — Studio frontend development

## Installation

### From PyPI

```bash
pip install hiveflow-core                  # core
pip install "hiveflow-core[security]"      # encryption + JSON schema
pip install "hiveflow-core[llm]"           # OpenAI + Anthropic clients
pip install "hiveflow-core[rag]"           # RAG utilities
pip install "hiveflow-core[all]"           # all optional extras
```

### From Source

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow/packages/core
pip install -e ".[dev]"
```

## Quick Start

HiveFlow is a **low-level orchestration engine**. You create agents with task handlers, schedule work with `ECM` messages, and read results from the shared blackboard.

### 1. Hello HiveFlow

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM


async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()

    try:
        async def greet_handler(ecm, view):
            message = f"Hello! Task: {ecm.intent}"
            await view.put("greeting_result", message)
            return {"message": message}

        await hf.create_agent(
            agent_id="greeter",
            skills={"greet"},
            read_keys=set(),
            write_keys={"greeting_result"},
            task_handler=greet_handler,
        )

        ecm = ECM(
            trace_id="hello-1",
            intent="Say hello",
            intent_id="intent-1",
            emitter="user",
            required_skills=["greet"],
            payload={"message": "Hello"},
        )
        await hf.scheduler.schedule(ecm)
        await asyncio.sleep(0.5)

        result = await hf.blackboard.sys_get("greeting_result")
        print(result)
    finally:
        await hf.shutdown()


asyncio.run(main())
```

**Runnable example:** `python examples/01_hello_hiveflow.py`

### 2. Multi-Agent Collaboration

Chain multiple agents by writing intermediate results to the blackboard and scheduling follow-up tasks. See `examples/02_multi_agent.py`.

### 3. Human-in-the-Loop

Use `HITLManager` to pause workflows until a human approves:

```python
from hiveflow import HITLManager, HITLAction

hitl = HITLManager()
gate = await hitl.create_gate(
    workflow_id="wf-1",
    node_id="review",
    action=HITLAction.APPROVAL,
    prompt="Approve this output?",
    context={"draft": "..."},
)
await hitl.respond(gate.gate_id, approved=True, comment="LGTM")
```

**Runnable example:** `python examples/03_hitl_approval.py`

### 4. Streaming Events

Use `StreamBuffer` to emit typed events (tokens, tool calls, node lifecycle):

```python
from hiveflow import StreamBuffer, StreamEvent, StreamEventType, collect_stream

buffer = StreamBuffer()
await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="Hello"))
await buffer.put(StreamEvent(type=StreamEventType.DONE, data=None))
await buffer.close()

events = await collect_stream(buffer)
```

**Runnable example:** `python examples/05_streaming.py`

## Example Cookbook

| Example | Topic |
|---------|-------|
| `01_hello_hiveflow.py` | First workflow |
| `02_multi_agent.py` | Multi-agent pipeline |
| `03_hitl_approval.py` | Human approval |
| `04_checkpoint.py` | Checkpoints & time travel |
| `05_streaming.py` | Streaming events |
| `06_rag_pipeline.py` | RAG pipeline |
| `07_mcp_tools.py` | MCP tool integration |
| `08_cognitive_planning.py` | Cognitive orchestrator |
| `09_evaluation.py` | Evaluation & A/B testing |
| `10_secure_blackboard.py` | Encrypted blackboard |
| `11_distributed_agents.py` | Redis-backed deployment |
| `12_custom_scheduler.py` | Custom scheduler strategy |
| `13_plugin_development.py` | Plugin marketplace |
| `14_guard_configuration.py` | Input/output guards |
| `15_multimodal_pipeline.py` | Image/audio/video processing |

Run any example from the repository root:

```bash
cd packages/core && pip install -e ".[all]"
cd ../../examples && python 01_hello_hiveflow.py
```

## Configuration

Copy the environment template:

```bash
cp .env.example .env
```

### Programmatic Configuration

```python
from hiveflow import HiveFlowConfig, SchedulerConfig

config = HiveFlowConfig(
    scheduler=SchedulerConfig(
        selection_strategy="least_loaded",
        default_intent_timeout=60.0,
    ),
    blackboard_type="memory",  # memory | ttl_memory | redis | encrypted
    worker_max_queue_size=100,
    log_level="INFO",
)
```

### Redis (Distributed)

```python
config = HiveFlowConfig(
    blackboard_type="redis",
    redis_url="redis://localhost:6379",
)
```

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## Next Steps

- [Core Concepts](concepts.md)
- [API Reference (auto-generated)](api/index.md)
- [Studio Agent cookbook](cookbook/studio-agent-mode.md)
- [Architecture](architecture.md)
- [Deployment](deployment.md)
- [Contributing](https://github.com/jdidjhdh/hiveflow/blob/main/CONTRIBUTING.md)

## Troubleshooting

**`No module named 'hiveflow'`** — Install from source with `pip install -e ".[dev]"` in `packages/core`.

**Optional feature ImportError** — Install the matching extra, e.g. `pip install "hiveflow-core[security]"`.

**Redis connection errors** — Ensure Redis is running (`redis-cli ping` → `PONG`).

<a id="studio-agent-mode"></a>

## Studio Agent mode

HiveFlow Studio switches between **Core DAG** and **HiveMind Agent** runtimes. Agent mode uses `HiveMindApp.run_query` to plan Skill graphs; with plan HITL enabled, review plan JSON on the **Approvals** page before execution.

### Environment variables

| Variable | Description |
|----------|-------------|
| `HIVEFLOW_RUNTIME=agent` | Default Agent runtime on startup |
| `HIVEFLOW_PLAN_HITL=true` | Require human approval before executing the plan graph |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | Echo LLM client when no API key (testing / CI) |
| `HIVEFLOW_LLM_PLANNING_PROVIDER` | LLM route for planning |
| `HIVEFLOW_LLM_EXECUTION_PROVIDER` | LLM route for execution |

### Local startup

```bash
# Backend (packages/studio/backend)
pip install -r requirements.txt
export HIVEFLOW_RUNTIME=agent
export HIVEFLOW_PLAN_HITL=true
export HIVEFLOW_AGENT_ECHO_LLM=true
uvicorn app.main:app --reload --port 8000

# Frontend (packages/studio/frontend)
npm install && npm run dev
```

Enable **real mode** in the Studio toolbar, switch **Orchestrator** to **Agent mode**, then use **Agent query** or **NL plan-only**.

### Related pages

- **Approvals** — review/edit `plan_approval` plan JSON
- **Analytics** — `/api/analytics/*` in real mode
- **Replay** — audit and checkpoints by `intent_id`
- **Tracer** — live WebSocket events; unified `intent_id` and `trace_id`

See [Studio Agent Operations](studio-agent-ops.md) and the [Complete Tutorial — Part 5](tutorial/part-5-studio.md).
