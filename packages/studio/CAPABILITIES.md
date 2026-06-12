# HiveFlow Studio — Feature Maturity Matrix

[English](#english) · [简体中文](#简体中文)

Studio v0.1.x is a **Technical Preview**. Use this matrix to set expectations for self-hosted and OSS deployments.

## English

### Maturity levels

| Level | Meaning |
|-------|---------|
| **Stable** | Core path; mock + real modes supported; suitable for PoC and internal ops |
| **Beta** | Works with backend in real mode; API or UX may change |
| **Preview** | UI prototype or local demo data only; not production-grade |
| **Demo** | Mock / simulated data only; no backend persistence |

### Page matrix

| Page | Route | Maturity | Mock mode | Real mode | Persistence |
|------|-------|----------|-----------|-----------|-------------|
| Orchestrator | `/orchestrator` | Stable | Local MockEngine + IndexedDB | API + WebSocket | IndexedDB + backend workflows |
| Agents | `/agents` | Stable | Local registry | Backend agents API | Backend |
| Chatflow | `/chatflow` | Beta | Local execution | Agent / API | IndexedDB |
| Approvals (HITL) | `/approvals` | Stable | Limited | Backend HITL | Backend |
| Variables | `/variables` | Beta | Local store | `GET/POST /api/variables` | Backend (real) / local (mock) |
| Triggers | `/triggers` | Beta | Local store | `GET/POST /api/triggers` | Backend (real) / local (mock) |
| Capability market | `/capabilities` | Beta | Demo plugin list | Marketplace API | Backend + local fallback |
| Dashboard | `/dashboard` | Beta | MockEngine metrics | `/api/metrics` + WS | — |
| Analytics | `/analytics` | Preview | Generated charts | Prometheus API | — |
| Tracer | `/tracer` | Beta | Event bus | Replay audit API | — |
| Replay | `/replay` | Beta | — | Backend replay | — |
| Blackboard | `/blackboard` | Stable | MockEngine | Backend / WS | Runtime |
| Events | `/events` | Stable | MockEngine bus | WebSocket | Session |
| LLM config | `/llm-config` | Beta | Local defaults | Backend config API | Partial |
| Knowledge base | `/knowledge` | Beta | Mock store | Backend KB API | Backend |
| Prompt templates | `/prompt-templates` | Preview | localStorage fallback | API when available | Partial |
| A/B testing | `/ab-testing` | Demo | **In-memory demo only** | Not wired | None |
| Audit log | `/audit-log` | Beta | — | Blackboard audit API | Read-only |
| Settings | `/settings` | Beta | MockEngine config | Partial | Engine config only |
| Orchestrator (Electron) | — | **Experimental** | — | Not in v0.1 release artifacts | — |

### Deployment notes

- **No built-in login** in v0.1.x — deploy behind VPN or reverse proxy. See [SECURITY.md](../../SECURITY.md).
- **Recommended**: `docker compose -f docker-compose.release.yml up` with tagged GHCR images (see [README.md](README.md)).
- **Desktop (Electron)**: experimental scripts only; not part of OSS v0.1 release artifacts.

---

## 简体中文

### 成熟度说明

| 等级 | 含义 |
|------|------|
| **Stable（稳定）** | 核心路径；支持 mock / real；可用于 PoC 与内网运维 |
| **Beta（测试）** | 真实模式可用；API 或体验可能变更 |
| **Preview（预览）** | 原型或演示数据为主；非生产级 |
| **Demo（演示）** | 仅本地模拟数据；无后端持久化 |

### 页面矩阵

| 页面 | 路由 | 成熟度 | 演示模式 | 真实模式 | 持久化 |
|------|------|--------|----------|----------|--------|
| 编排器 | `/orchestrator` | Stable | MockEngine + IndexedDB | API + WebSocket | IndexedDB + 后端工作流 |
| Agent 管理 | `/agents` | Stable | 本地注册表 | 后端 API | 后端 |
| 对话式工作流 | `/chatflow` | Beta | 本地执行 | Agent / API | IndexedDB |
| 人工审批 | `/approvals` | Stable | 有限 | 后端 HITL | 后端 |
| 变量 | `/variables` | Beta | 本地 store | `/api/variables` | 真实模式走后端 |
| 触发器 | `/triggers` | Beta | 本地 store | `/api/triggers` | 真实模式走后端 |
| 能力市场 | `/capabilities` | Beta | 演示插件列表 | Marketplace API | 后端 + 本地回退 |
| 仪表盘 | `/dashboard` | Beta | Mock 指标 | `/api/metrics` + WS | — |
| 执行分析 | `/analytics` | Preview | 生成图表 | Prometheus API | — |
| 任务追踪 | `/tracer` | Beta | 事件总线 | 审计 API | — |
| 执行回放 | `/replay` | Beta | — | 后端回放 | — |
| 黑板 | `/blackboard` | Stable | MockEngine | 后端 / WS | 运行时 |
| 事件流 | `/events` | Stable | Mock 总线 | WebSocket | 会话 |
| LLM 模型 | `/llm-config` | Beta | 本地默认 | 后端配置 API | 部分 |
| 知识库 | `/knowledge` | Beta | Mock | 后端 KB API | 后端 |
| Prompt 模板 | `/prompt-templates` | Preview | localStorage | API（可用时） | 部分 |
| A/B 测试 | `/ab-testing` | Demo | **仅内存演示** | 未对接 | 无 |
| 审计日志 | `/audit-log` | Beta | — | 黑板审计 API | 只读 |
| 设置 | `/settings` | Beta | MockEngine | 部分 | 仅引擎配置 |
| Electron 桌面版 | — | **Experimental** | — | 不含于 v0.1 制品 | — |

### 部署提示

- v0.1.x **无内置登录**，请部署在内网或通过反向代理。详见 [SECURITY.md](../../SECURITY.md)。
- **推荐**：使用 `docker-compose.release.yml` 拉取 GHCR 固定版本镜像。
- **Electron**：实验性脚本，不属于 v0.1 开源发布制品。
