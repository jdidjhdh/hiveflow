<p align="center">
  <a href="README.md">English</a> · <a href="README.zh.md">简体中文</a>
</p>

<p align="center">
  <img src="docs/assets/logo.svg" alt="HiveFlow" width="80"/>
</p>

<h1 align="center">HiveFlow</h1>

<p align="center">
  <strong>多 Agent 协调与 HITL 层 — 自带可视化 Studio 与 MCP 工具。</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/hiveflow-core/"><img src="https://img.shields.io/pypi/v/hiveflow-core.svg" alt="PyPI"/></a>
  <a href="https://pypi.org/project/hiveflow-core/"><img src="https://img.shields.io/pypi/pyversions/hiveflow-core.svg" alt="Python"/></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT"/></a>
  <a href="https://github.com/jdidjhdh/hiveflow/actions/workflows/test.yml"><img src="https://github.com/jdidjhdh/hiveflow/actions/workflows/test.yml/badge.svg" alt="Tests"/></a>
  <a href="https://jdidjhdh.github.io/hiveflow/en/"><img src="https://img.shields.io/badge/docs-English-blue" alt="Docs EN"/></a>
  <a href="https://jdidjhdh.github.io/hiveflow/zh/"><img src="https://img.shields.io/badge/docs-中文-blue" alt="Docs ZH"/></a>
</p>

> **0.1.x Alpha** — [v0.1.0 发布](https://github.com/jdidjhdh/hiveflow/releases/tag/v0.1.0) · [版本策略](docs/zh/versioning.md) · [文档](https://jdidjhdh.github.io/hiveflow/zh/) · [参与贡献](CONTRIBUTING.md#edit-without-being-a-collaborator)（Fork / 编辑文档 / 讨论）

HiveFlow 是面向多 Agent 场景的**协调与 HITL 层**：人工审批、可审计共享状态、自托管运维 UI —— 并可通过 [LangGraph Sidecar](docs/zh/cookbook/langgraph-sidecar.md) 与 LangGraph 等运行时兼容共存。

### 为什么选择 HiveFlow？

| 差异化 | 你得到什么 |
|--------|------------|
| **协调层** | 调度、黑板、HITL — 原生运行时或 [LangGraph Sidecar](docs/zh/cookbook/langgraph-sidecar.md) |
| **Human-in-the-Loop** | 计划与动作门控，Studio 审批页 + 超时策略 |
| **可视化 Studio** | 编排器、Chatflow、Analytics、Replay、HITL — 可自托管 |
| **安全** | 双 Guard + 可审计、可加密黑板 |
| **MCP 原生** | 统一工具协议与插件市场钩子 |

---

## Golden Path（约 5 分钟）

**在 Studio Agent 模式下体验 HiveFlow：** 自然语言 → 规划 → 画布 → 执行。`docker-compose.yml` 默认开启 `HIVEFLOW_AGENT_ECHO_LLM=true`，无需 API Key。

### 1. Docker（推荐）

```bash
git clone https://github.com/jdidjhdh/hiveflow.git
cd hiveflow
docker compose up --build
```

打开 **http://localhost:3000** → **Orchestrator（编排器）** → 开启 **Agent / real mode**。

| 步骤 | 操作 |
|------|------|
| 1 | 输入目标（例如：*总结 AI Agent 领域的三个趋势*） |
| 2 | 点击 **Plan only（仅规划）** 并查看 TaskGraph |
| 3 | **导入到画布** → **执行 DAG** |

API：`POST /api/agent/plan-only` · `execute-plan` · `query` — 见 [Studio Agent 指南](docs/zh/cookbook/studio-agent-mode.md)（[English](docs/en/cookbook/studio-agent-mode.md)）。

### 2. PyPI（库 / 脚本）

```bash
pip install hiveflow-core hiveflow-agent
python examples/01_hello_hiveflow.py
```

可选扩展：`pip install "hiveflow-core[all]"`（security、llm、rag、redis）。

### 进阶 — 仅嵌入 Core 引擎

不依赖 Studio 的底层控制：注册 Agent、调度 `ECM` 任务、读写黑板。

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM

async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()
    try:
        async def handler(ecm, view):
            await view.put("result", f"Done: {ecm.intent}")
            return {"status": "ok"}

        await hf.create_agent(
            agent_id="worker",
            skills={"process"},
            read_keys=set(),
            write_keys={"result"},
            task_handler=handler,
        )
        await hf.scheduler.schedule(ECM(
            trace_id="demo-1",
            intent="Research AI trends",
            intent_id="task-1",
            emitter="user",
            required_skills=["process"],
        ))
        await asyncio.sleep(0.5)
        print(await hf.blackboard.sys_get("result"))
    finally:
        await hf.shutdown()

asyncio.run(main())
```

→ [`examples/01_hello_hiveflow.py`](examples/01_hello_hiveflow.py) · [Core README](packages/core/README.zh.md)

---

## 功能概览

| 领域 | 能力 |
|------|------|
| 编排 | 静态/动态 DAG、认知规划、三种调度策略 |
| 协作 | 事件总线、Skill 路由、多 Agent 黑板 |
| HITL | 审批门、计划审阅、Studio + WebSocket 通知 |
| 数据 | RAG、Checkpoint（时光回溯）、SSE 流式 |
| 工具 | MCP 协议、插件市场、ReAct Worker |
| 运维 | Studio UI、Prometheus 分析、Trace 回放 |

---

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    HiveFlow Studio（Web UI）                 │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST + WebSocket
┌─────────────────────────────▼───────────────────────────────┐
│                   HiveFlow Agent 运行时                      │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│         HiveFlow Core（调度、HITL、RAG、MCP）                 │
└─────────────────────────────────────────────────────────────┘
```

详情：[架构（中文）](docs/zh/architecture.md) · [Architecture (EN)](docs/en/architecture.md)

---

## 三大模块

HiveFlow 是包含三个包的 monorepo。按集成深度选择层级。

| 模块 | 包 | 角色 | 典型用户 |
|------|-----|------|----------|
| **Core** | [`hiveflow`](packages/core/) · PyPI | 编排内核 — 调度、黑板、DAG/HITL/RAG/MCP | 库作者、后端工程师 |
| **Agent** | [`hiveflow-agent`](packages/agent/) · PyPI | 自然语言规划 + Core 之上认知 Skill 图 | Agent 开发者、LLM 应用开发者 |
| **Studio** | [`packages/studio`](packages/studio/) · 自托管 | 可视化运维 UI + FastAPI（REST/WS） | 运维、审批人、全栈团队 |

### Core — `packages/core`（`hiveflow`）

**可嵌入引擎**。注册带 Skill 的 Worker，调度 `ECM`，通过共享黑板协同。含静态/动态 DAG、HITL、Checkpoint、双 Guard、RAG、MCP 与指标 — 不依赖 UI。

- **安装：** `pip install hiveflow-core` · **文档：** [Core README（中文）](packages/core/README.zh.md) · [API](docs/zh/api/index.md)

### Agent — `packages/agent`（`hiveflow-agent`）

Core 之上的**认知运行时**。`HiveMindApp` 将自然语言转为 TaskGraph，绑定 ReAct Skill 并执行。支持 plan-only、`run_query`、`execute_plan`，可选计划 HITL。

- **安装：** `pip install hiveflow-agent` · **文档：** [Agent README（中文）](packages/agent/README.zh.md)

### Studio — `packages/studio`（FastAPI + React）

**可视化运维平台**。编排器、Chatflow、审批、Analytics、Tracer、Replay；后端桥接 Core DAG 与 Agent 模式，支持 LangGraph 计划导出。

- **本地运行：** `docker compose up` 或 `uvicorn` + `npm run dev`
- **生产镜像：** `v*` 标签发布至 GHCR — 见 [`docker-compose.release.yml`](../../docker-compose.release.yml)
- **功能成熟度：** [CAPABILITIES.md](packages/studio/CAPABILITIES.md)（各页面 Stable / Beta / Preview / Demo）
- **文档：** [Studio README（中文）](packages/studio/README.zh.md)

> **v0.1.x 技术预览：** Studio 无内置登录，请部署在内网或反向代理之后。Electron 桌面脚本为**实验性**，不属于发布制品。

---

## 文档

| 资源 | English | 中文 |
|------|---------|------|
| 文档站 | [en/](https://jdidjhdh.github.io/hiveflow/en/) | [zh/](https://jdidjhdh.github.io/hiveflow/zh/) |
| 快速入门 | [docs/en/getting-started.md](docs/en/getting-started.md) | [docs/zh/getting-started.md](docs/zh/getting-started.md) |
| 三大模块 | [Core](packages/core/README.md) · [Agent](packages/agent/README.md) · [Studio](packages/studio/README.md) | [Core](packages/core/README.zh.md) · [Agent](packages/agent/README.zh.md) · [Studio](packages/studio/README.zh.md) |
| 实践指南 | [docs/en/cookbook/](docs/en/cookbook/) | [docs/zh/cookbook/](docs/zh/cookbook/) |

---

## 项目结构

```
HiveFlow/
├── packages/core/          # PyPI: hiveflow
├── packages/agent/         # PyPI: hiveflow-agent
├── packages/studio/        # 自托管 UI + 后端
├── examples/               # 16 个 smoke 示例
└── docs/                   # MkDocs（en/ + zh/）
```

---

## 开发

```bash
cd packages/core && pip install -e ".[dev]" && pytest
cd packages/studio/backend && HIVEFLOW_AGENT_ECHO_LLM=true pytest tests/
cd packages/studio/frontend && npm ci && npm run lint && npm run test:unit && npm run build
pip install mkdocs-material "mkdocstrings[python]" mkdocs-static-i18n && pip install -e packages/core
python -m mkdocs build --strict
```

请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) · [文档 i18n 说明](docs/zh/i18n.md)

---

## 对比

| 功能 | HiveFlow | LangGraph | CrewAI | AutoGen |
|------|:--------:|:---------:|:------:|:-------:|
| 动态编排 | ✅ | ⚠️ | ❌ | ⚠️ |
| Human-in-the-Loop | ✅ | ⚠️ | ❌ | ⚠️ |
| Checkpoint / 回放 | ✅ | ✅ | ❌ | ❌ |
| 安全 Guard | ✅ | ❌ | ❌ | ❌ |
| MCP 协议 | ✅ | ❌ | ❌ | ❌ |
| 可视化运维 UI | ✅ | 💰 | ❌ | ❌ |

---

## 许可证

MIT — 见 [LICENSE](LICENSE)。

## 致谢

受 LangGraph、CrewAI、AutoGen 启发 · 基于 [MCP](https://github.com/modelcontextprotocol) · Studio UI 使用 [Ant Design](https://ant.design/) 与 [React](https://react.dev/)
