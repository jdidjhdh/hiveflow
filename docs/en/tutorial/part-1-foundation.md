# Part 1 — Foundation

Install HiveFlow, understand the repository layout, and run your first workflow.

## 1.1 Installation paths

### Path A — Docker (recommended for Studio)

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
cp .env.example .env   # optional: set API keys
docker compose up --build
```

| Service | URL |
|---------|-----|
| Studio UI | http://localhost:3000 |
| API | http://localhost:8000 |
| Redis | localhost:6379 |
| Postgres | localhost:5432 |

Default `docker-compose.yml` sets `HIVEFLOW_AGENT_ECHO_LLM=true` so you can use Agent mode **without** an LLM API key.

### Path B — PyPI (library only)

```bash
pip install hiveflow-core hiveflow-agent
```

Optional extras:

```bash
pip install "hiveflow-core[security]"   # encryption, JSON schema
pip install "hiveflow-core[llm]"        # OpenAI + Anthropic
pip install "hiveflow-core[rag]"        # RAG utilities
pip install "hiveflow-core[all]"        # everything
```

### Path C — Editable source (contributors)

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
pip install -e packages/core -e packages/agent
pip install -e "packages/core[all]"
```

## 1.2 Repository layout

```
hiveflow/
├── packages/core/       # Orchestration kernel (hiveflow-core)
├── packages/agent/      # NL planning + LLM (hiveflow-agent)
├── packages/studio/     # FastAPI backend + React frontend
├── examples/            # 16 runnable tutorials
├── docs/                # MkDocs (en/ + zh/)
├── scripts/             # Release, CI, debug utilities
├── docker-compose.yml   # Full local stack
└── kubernetes/          # K8s deployment manifest
```

**Three layers:**

| Layer | Package | Role |
|-------|---------|------|
| Core | `hiveflow-core` | Scheduler, blackboard, DAG, HITL, MCP — no UI |
| Agent | `hiveflow-agent` | Natural-language planning, ReAct worker, LLM routing |
| Studio | `packages/studio` | Visual ops UI on top of Core + Agent |

## 1.3 Core concepts (minimal)

Before coding, know these four primitives:

| Primitive | Purpose |
|-----------|---------|
| **ECM** | Event-Condition-Message — a unit of work sent to the scheduler |
| **Cell / Agent** | Worker with skills, read/write keys, and a `task_handler` |
| **Blackboard** | Shared key-value store between agents |
| **Scheduler** | Routes ECM to agents by required skills |

See [Concepts](../concepts.md) for full definitions.

## 1.4 Your first workflow (Example 01)

Create `hello.py` or run the built-in example:

```bash
python examples/01_hello_hiveflow.py
```

Expected output:

```
Task scheduled: True
Workflow completed!
Result: Hello from user! Task: Say hello to the world
```

### Step-by-step

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM

async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()
    try:
        async def greet_handler(ecm, view):
            message = f"Hello from {ecm.emitter}! Task: {ecm.intent}"
            await view.put("greeting_result", message)
            return {"message": message}

        await hf.create_agent(
            agent_id="greeter",
            skills={"greet", "respond"},
            read_keys=set(),
            write_keys={"greeting_result"},
            task_handler=greet_handler,
        )

        ecm = ECM(
            trace_id="hello-1",
            intent="Say hello to the world",
            intent_id="intent-1",
            emitter="user",
            required_skills=["greet"],
            payload={"message": "Hello"},
        )
        await hf.scheduler.schedule(ecm)
        await asyncio.sleep(0.5)
        print(await hf.blackboard.sys_get("greeting_result"))
    finally:
        await hf.shutdown()

asyncio.run(main())
```

### What happens internally

1. `HiveFlow.start()` boots the event bus, scheduler, and blackboard.
2. `create_agent()` registers a Cell with skills and ACL keys.
3. `scheduler.schedule(ecm)` picks the greeter (only agent with `greet` skill).
4. The handler writes to the blackboard via `view.put()`.
5. `shutdown()` drains queues and closes connections.

## 1.5 Configuration basics

Copy environment template:

```bash
cp .env.example .env
```

Programmatic config:

```python
from hiveflow import HiveFlowConfig, SchedulerConfig

config = HiveFlowConfig(
    scheduler=SchedulerConfig(
        selection_strategy="least_loaded",  # or "auction", "load_aware"
        default_intent_timeout=60.0,
    ),
    blackboard_type="memory",  # memory | ttl_memory | redis | encrypted
    log_level="INFO",
)
```

## 1.6 Exercises

1. Add a second agent with skill `respond` that reads `greeting_result` and writes `final_reply`.
2. Change `selection_strategy` to `"auction"` and observe logs.
3. Set `blackboard_type="ttl_memory"` and inspect TTL behavior in [Part 3](part-3-advanced.md).

## Next

→ [Part 2 — Workflows](part-2-workflows.md): multi-agent pipelines, HITL, streaming, RAG.
