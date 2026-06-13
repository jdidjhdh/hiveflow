# 第 1 部分 — 基础

安装 HiveFlow、理解仓库结构，并运行第一个工作流。

## 1.1 安装方式

### 方式 A — Docker（推荐，含 Studio）

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
cp .env.example .env   # 可选：配置 API Key
docker compose up --build
```

| 服务 | 地址 |
|------|------|
| Studio UI | http://localhost:3000 |
| API | http://localhost:8000 |
| Redis | localhost:6379 |
| Postgres | localhost:5432 |

默认 `docker-compose.yml` 设置 `HIVEFLOW_AGENT_ECHO_LLM=true`，**无需** LLM API Key 即可使用 Agent 模式。

### 方式 B — PyPI（仅库）

```bash
pip install hiveflow-core hiveflow-agent
```

可选扩展：

```bash
pip install "hiveflow-core[security]"   # 加密、JSON Schema
pip install "hiveflow-core[llm]"        # OpenAI + Anthropic
pip install "hiveflow-core[rag]"        # RAG 工具
pip install "hiveflow-core[all]"        # 全部
```

### 方式 C — 源码可编辑安装（贡献者）

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
pip install -e packages/core -e packages/agent
pip install -e "packages/core[all]"
```

## 1.2 仓库结构

```
hiveflow/
├── packages/core/       # 编排内核（hiveflow-core）
├── packages/agent/      # NL 规划 + LLM（hiveflow-agent）
├── packages/studio/     # FastAPI 后端 + React 前端
├── examples/            # 16 个可运行教程
├── docs/                # MkDocs 文档（en/ + zh/）
├── scripts/             # 发布、CI、调试脚本
├── docker-compose.yml   # 本地全栈
└── kubernetes/          # K8s 部署清单
```

**三层架构：**

| 层 | 包 | 职责 |
|----|-----|------|
| Core | `hiveflow-core` | 调度、黑板、DAG、HITL、MCP — 无 UI |
| Agent | `hiveflow-agent` | 自然语言规划、ReAct Worker、LLM 路由 |
| Studio | `packages/studio` | 可视化运维 UI |

## 1.3 核心概念（最小集）

编码前先了解四个原语：

| 原语 | 作用 |
|------|------|
| **ECM** | Event-Condition-Message — 发送给调度器的工作单元 |
| **Cell / Agent** | 带 skills、读写键和 `task_handler` 的 Worker |
| **Blackboard（黑板）** | Agent 间共享的键值存储 |
| **Scheduler（调度器）** | 按 required_skills 将 ECM 路由到 Agent |

完整定义见 [核心概念](../concepts.md)。

## 1.4 第一个工作流（示例 01）

运行内置示例：

```bash
python examples/01_hello_hiveflow.py
```

预期输出：

```
Task scheduled: True
Workflow completed!
Result: Hello from user! Task: Say hello to the world
```

### 分步说明

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

### 内部流程

1. `HiveFlow.start()` 启动事件总线、调度器、黑板。
2. `create_agent()` 注册带 skills 和 ACL 键的 Cell。
3. `scheduler.schedule(ecm)` 选中 greeter（唯一具备 `greet` skill 的 Agent）。
4. Handler 通过 `view.put()` 写入黑板。
5. `shutdown()` 排空队列并关闭连接。

## 1.5 基础配置

复制环境变量模板：

```bash
cp .env.example .env
```

编程式配置：

```python
from hiveflow import HiveFlowConfig, SchedulerConfig

config = HiveFlowConfig(
    scheduler=SchedulerConfig(
        selection_strategy="least_loaded",  # 或 "auction"、"load_aware"
        default_intent_timeout=60.0,
    ),
    blackboard_type="memory",  # memory | ttl_memory | redis | encrypted
    log_level="INFO",
)
```

## 1.6 练习

1. 添加第二个 Agent，skill 为 `respond`，读取 `greeting_result` 并写入 `final_reply`。
2. 将 `selection_strategy` 改为 `"auction"`，观察日志。
3. 设置 `blackboard_type="ttl_memory"`，在 [第 3 部分](part-3-advanced.md) 了解 TTL 行为。

## 下一步

→ [第 2 部分 — 工作流](part-2-workflows.md)：多 Agent 流水线、HITL、流式、RAG。
