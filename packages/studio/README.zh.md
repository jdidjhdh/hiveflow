# HiveFlow Studio

[English](README.md) · **简体中文**

**路径：** `packages/studio` · **未发布 PyPI** · **技术栈：** FastAPI（后端）+ React / TypeScript（前端）

HiveFlow 的自托管可视化运维平台。Studio 让团队在画布上设计工作流，在 Core DAG 与 Agent 运行时之间切换，审批计划与操作（HITL），并通过分析、追踪与回放检查运行——无需专有云服务层。

## 功能概览

| 领域 | 页面 / 功能 |
|------|-------------|
| **设计** | Orchestrator（ReactFlow DAG）、Chatflow（对话流）、模板、导入/导出（`.hflow`） |
| **Agent 模式** | NL `run_query`、`plan-only`、画布 `execute-plan`、LangGraph 导出 |
| **HITL** | 审批（计划 + 节点门控）、WebSocket `hitl.pending` 通知 |
| **可观测性** | Dashboard、Analytics（Prometheus）、Tracer、Replay（`intent_id` / 审计） |
| **平台** | Blackboard 查看器、变量、插件/MCP 市场、知识库、检查点 |
| **运行时桥接** | `EngineService` — Core 工作流 **或** 当 `HIVEFLOW_RUNTIME=agent` 时使用 `HiveMindApp` |

## 架构

```
packages/studio/
├── backend/          # FastAPI — /api/*, WebSocket /ws
│   └── app/
│       ├── api/      # workflows, agent, hitl, analytics, replay, …
│       └── core/     # EngineService, agent runtime wiring
└── frontend/         # Vite + React + Ant Design + ReactFlow
    └── src/pages/    # Orchestrator, Chatflow, Approvals, …
```

后端依赖可编辑安装的 [`../core`](../core/README.md) 与 [`../agent`](../agent/README.md)。

## 何时使用 Studio

- 运维与审核人员需要 UI，而不仅是 Python API
- 受监管工作流需要计划审批与审计追踪
- 可视化调试：节点状态、日志、按 `intent_id` 回放
- 同一仓库演示：`docker compose up` 启动完整栈

若仅需库级嵌入，可不使用 Studio，直接使用 [Core](../core/README.md) 或 [Agent](../agent/README.md)。

## 快速开始

### Docker Compose（推荐）

```bash
docker compose up studio frontend
```

默认环境：`HIVEFLOW_RUNTIME=agent`、`HIVEFLOW_PLAN_HITL=true`、`HIVEFLOW_AGENT_ECHO_LLM=true`。

### 手动启动

```bash
# Backend
cd packages/studio/backend
pip install -r requirements.txt
set HIVEFLOW_RUNTIME=agent          # Windows
set HIVEFLOW_AGENT_ECHO_LLM=true
uvicorn app.main:app --reload --port 8000

# Frontend
cd packages/studio/frontend
npm install && npm run dev
```

打开 `http://localhost:3000`。在页头启用 **real mode**，然后使用 Orchestrator → Agent 抽屉或工具栏。

## Agent HTTP API（后端）

| 端点 | 说明 |
|------|------|
| `GET/POST /api/agent/runtime` | Core 与 Agent 模式切换 |
| `POST /api/agent/query` | 完整 NL 查询并执行 |
| `POST /api/agent/plan-only` | 仅生成 TaskGraph |
| `POST /api/agent/execute-plan` | 执行画布 / 导入的计划 |
| `POST /api/agent/export-langgraph` | 导出计划为 LangGraph JSON（+ 可选 Python 桩代码） |

## 功能成熟度

Studio v0.1.x 为**技术预览**。各页面在 UI 中标注成熟度（Stable / Beta / Preview / Demo），完整矩阵见 **[CAPABILITIES.md](CAPABILITIES.md)**。

| 等级 | 含义 |
|------|------|
| Stable | 核心路径；支持 mock + real |
| Beta | 真实模式可用；API 可能变更 |
| Preview | 原型或部分持久化 |
| Demo | 仅内存 / 本地演示数据 |

## 生产部署

使用 GHCR 固定版本镜像（在 `v*` 标签发布时构建）：

```bash
export HIVEFLOW_VERSION=0.1.0
export HIVEFLOW_IMAGE_OWNER=your-github-org   # 小写
docker compose -f docker-compose.release.yml up -d
```

镜像：`ghcr.io/<owner>/hiveflow-studio-api:<version>` · `ghcr.io/<owner>/hiveflow-studio-web:<version>`

**安全：** v0.1.x **无内置鉴权**。见 [SECURITY.md](../../SECURITY.md) 与下方 [部署安全](#部署安全)。

## 部署安全

- 勿在无鉴权反向代理的情况下将 `8000` 端口暴露到公网。
- 非本地环境请修改 `docker-compose.release.yml` 中的默认 `POSTGRES_PASSWORD`。
- Mock / Demo 页面（如 A/B 测试）不可用于生产 — 见 [CAPABILITIES.md](CAPABILITIES.md)。
- **Electron**（`npm run electron:*`）为实验性功能，不属于 v0.1 发布制品。

## 开发

```bash
# 后端（覆盖率 ≥ 60%）
cd packages/studio/backend
HIVEFLOW_AGENT_ECHO_LLM=true pytest tests/ --cov=app --cov-fail-under=60

# 前端单测（utils/stores ~24% 行门禁；页面见 E2E）
cd packages/studio/frontend
npm ci && npm run lint && npm run test:coverage && npm run build

# E2E
npm run test:e2e
```

### 分发与覆盖率策略

Studio **不**作为独立 PyPI/npm 包发布（0.1.x），通过 **monorepo** 或 **Docker** 使用。

Vitest 排除 `src/pages/**` 与编排器 hooks；这些路由由 **17 个 Playwright E2E** 覆盖，UI 标注成熟度。见 **[CAPABILITIES.md](CAPABILITIES.md)**。

完整矩阵：[质量门禁](https://hiveflow.github.io/hiveflow/zh/quality-gates/)。

## 文档

- [Studio Agent operations](https://hiveflow.github.io/hiveflow/studio-agent-ops/)
- [Studio Agent cookbook](https://hiveflow.github.io/hiveflow/cookbook/studio-agent-mode/)
- [Architecture — Studio layer](https://hiveflow.github.io/hiveflow/architecture/)
- [Main repository README](../../README.md)

## 许可证

MIT — 与 HiveFlow 项目根目录相同。
