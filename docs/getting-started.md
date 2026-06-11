# Getting Started with HiveFlow

This guide will help you get up and running with HiveFlow in minutes.

## Prerequisites

- **Python 3.10+**
- **pip**
- **(Optional) Redis** — distributed blackboard and event bus
- **(Optional) Node.js 18+** — Studio frontend development

## Installation

### From PyPI

```bash
pip install hiveflow                  # core
pip install "hiveflow[security]"      # encryption + JSON schema
pip install "hiveflow[llm]"           # OpenAI + Anthropic clients
pip install "hiveflow[rag]"           # RAG utilities
pip install "hiveflow[all]"           # all optional extras
```

### From Source

```bash
git clone https://github.com/hiveflow/hiveflow.git
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
- [Contributing](https://github.com/hiveflow/hiveflow/blob/main/CONTRIBUTING.md)

## Troubleshooting

**`No module named 'hiveflow'`** — Install from source with `pip install -e ".[dev]"` in `packages/core`.

**Optional feature ImportError** — Install the matching extra, e.g. `pip install "hiveflow[security]"`.

**Redis connection errors** — Ensure Redis is running (`redis-cli ping` → `PONG`).

<a id="studio-agent-mode"></a>

## Studio Agent 模式

HiveFlow Studio 可在 **Core DAG** 与 **HiveMind Agent** 两种运行时之间切换。Agent 模式使用 `HiveMindApp.run_query` 自动规划 Skill 图；开启计划 HITL 后，执行前需在「人工审批」页审阅计划 JSON。

### 环境变量

| 变量 | 说明 |
|------|------|
| `HIVEFLOW_RUNTIME=agent` | 启动时默认 Agent 模式 |
| `HIVEFLOW_PLAN_HITL=true` | 执行前需人工审批计划图 |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | 无 LLM 时使用 Echo 客户端（测试/联调） |
| `HIVEFLOW_LLM_PLANNING_PROVIDER` | 规划阶段 LLM 路由 |
| `HIVEFLOW_LLM_EXECUTION_PROVIDER` | 执行阶段 LLM 路由 |

### 本地启动

```bash
# 后端（packages/studio/backend）
pip install -r requirements.txt
$env:HIVEFLOW_RUNTIME="agent"
$env:HIVEFLOW_PLAN_HITL="true"
$env:HIVEFLOW_AGENT_ECHO_LLM="true"
uvicorn app.main:app --reload --port 8000

# 前端（packages/studio/frontend）
npm install && npm run dev
```

在 Studio 顶栏打开**真实模式**，编排器内切换 **Agent 模式**，使用「Agent 查询」或「NL 生成草图（plan-only）」。

### 相关页面

- **人工审批** — 审阅/编辑 `plan_approval` 计划 JSON
- **执行分析** — 真实模式下读取 `/api/analytics/*`
- **执行回放** — 按 `intent_id` 查看 audit 与 checkpoint
- **任务追踪** — 实时 WS 事件，`intent_id` 与 `trace_id` 已统一

详见 [Studio Agent 运维](studio-agent-ops.md)。
