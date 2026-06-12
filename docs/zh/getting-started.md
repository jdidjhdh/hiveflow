# HiveFlow 快速入门

本指南将帮助你在几分钟内上手 HiveFlow。

## Golden Path — Studio Agent 模式

最快体验 HiveFlow 的方式：启动 Studio + Agent 运行时，用自然语言生成计划，导入画布并执行。

### Docker（推荐）

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
docker compose up --build
```

打开 **http://localhost:3000** → **Orchestrator（编排器）** → 开启 **Agent / real mode** → **Plan only** → **导入到画布** → **执行 DAG**。

详见 [Studio Agent 指南](cookbook/studio-agent-mode.md)。

### PyPI 快速验证

```bash
pip install hiveflow-core hiveflow-agent
python examples/01_hello_hiveflow.py
```

---

## 前置条件

- **Python 3.10+**
- **pip**
- **（可选）Redis** — 分布式黑板与事件总线
- **（可选）Node.js 18+** — Studio 前端开发

## 安装

### 从 PyPI 安装

```bash
pip install hiveflow-core                  # core
pip install "hiveflow-core[security]"      # encryption + JSON schema
pip install "hiveflow-core[llm]"           # OpenAI + Anthropic clients
pip install "hiveflow-core[rag]"           # RAG utilities
pip install "hiveflow-core[all]"           # all optional extras
```

### 从源码安装

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow/packages/core
pip install -e ".[dev]"
```

## 快速开始

HiveFlow 是一个**底层编排引擎**。你需要创建带任务处理器的 Agent，使用 `ECM` 消息调度工作，并从共享黑板读取结果。

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

**可运行示例：** `python examples/01_hello_hiveflow.py`

### 2. 多智能体协作

将中间结果写入黑板并调度后续任务，即可串联多个 Agent。参见 `examples/02_multi_agent.py`。

### 3. Human-in-the-Loop（人机协同）

使用 `HITLManager` 暂停工作流，直到人工审批：

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

**可运行示例：** `python examples/03_hitl_approval.py`

### 4. 流式事件

使用 `StreamBuffer` 发送类型化事件（token、工具调用、节点生命周期）：

```python
from hiveflow import StreamBuffer, StreamEvent, StreamEventType, collect_stream

buffer = StreamBuffer()
await buffer.put(StreamEvent(type=StreamEventType.TOKEN, data="Hello"))
await buffer.put(StreamEvent(type=StreamEventType.DONE, data=None))
await buffer.close()

events = await collect_stream(buffer)
```

**可运行示例：** `python examples/05_streaming.py`

## 示例 Cookbook

| 示例 | 主题 |
|---------|-------|
| `01_hello_hiveflow.py` | 第一个工作流 |
| `02_multi_agent.py` | 多智能体流水线 |
| `03_hitl_approval.py` | 人工审批 |
| `04_checkpoint.py` | 检查点与时间旅行 |
| `05_streaming.py` | 流式事件 |
| `06_rag_pipeline.py` | RAG 流水线 |
| `07_mcp_tools.py` | MCP 工具集成 |
| `08_cognitive_planning.py` | 认知编排器 |
| `09_evaluation.py` | 评估与 A/B 测试 |
| `10_secure_blackboard.py` | 加密黑板 |
| `11_distributed_agents.py` | Redis 部署 |
| `12_custom_scheduler.py` | 自定义调度策略 |
| `13_plugin_development.py` | 插件市场 |
| `14_guard_configuration.py` | 输入/输出守卫 |
| `15_multimodal_pipeline.py` | 图像/音频/视频处理 |

从仓库根目录运行任意示例：

```bash
cd packages/core && pip install -e ".[all]"
cd ../../examples && python 01_hello_hiveflow.py
```

## 配置

复制环境变量模板：

```bash
cp .env.example .env
```

### 编程式配置

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

### Redis（分布式）

```python
config = HiveFlowConfig(
    blackboard_type="redis",
    redis_url="redis://localhost:6379",
)
```

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## 下一步

- [核心概念](concepts.md)
- [API 参考（自动生成）](api/index.md)
- [Studio Agent 指南](cookbook/studio-agent-mode.md)
- [架构](architecture.md)
- [部署](deployment.md)
- [贡献指南](https://github.com/jdidjhdh/hiveflow/blob/main/CONTRIBUTING.md)

## 故障排查

**`No module named 'hiveflow'`** — 在 `packages/core` 目录下使用 `pip install -e ".[dev]"` 从源码安装。

**可选功能 ImportError** — 安装对应的 extra，例如 `pip install "hiveflow-core[security]"`。

**Redis 连接错误** — 确保 Redis 正在运行（`redis-cli ping` → `PONG`）。

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
