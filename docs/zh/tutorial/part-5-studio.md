# 第 5 部分 — Studio

HiveFlow Studio 自托管运维 UI 完整 walkthrough。

## 5.1 启动 Studio

### Docker（最简单）

```bash
docker compose up --build
```

| 地址 | 用途 |
|------|------|
| http://localhost:3000 | React 前端 |
| http://localhost:8000 | FastAPI 后端 |
| http://localhost:8000/docs | OpenAPI Swagger |

### 本地开发（两个终端）

```bash
# 终端 1 — 后端
cd packages/studio/backend
pip install -r requirements.txt
export HIVEFLOW_RUNTIME=agent
export HIVEFLOW_AGENT_ECHO_LLM=true
export HIVEFLOW_PLAN_HITL=true
uvicorn app.main:app --reload --port 8000

# 终端 2 — 前端
cd packages/studio/frontend
npm install && npm run dev
```

## 5.2 Golden Path — Agent 模式

1. 打开 **Orchestrator（编排器）**。
2. 在工具栏开启 **Agent / real mode**。
3. 输入目标：*Summarize three trends in AI agents*（或中文目标）。
4. 点击 **Plan only（仅规划）** — 审阅生成的 TaskGraph。
5. 点击 **导入到画布**。
6. 点击 **执行 DAG**。

启用 `HIVEFLOW_PLAN_HITL=true` 时，第 4 步会在 **Approvals（人工审批）** 创建 gate，执行前需审批。

深度阅读：[Studio Agent 模式 Cookbook](../cookbook/studio-agent-mode.md)。

## 5.3 Studio 页面参考

| 页面 | 功能 |
|------|------|
| **Dashboard（仪表盘）** | 系统概览、近期活动 |
| **Orchestrator（编排器）** | DAG 画布、Agent 抽屉、规划/执行 |
| **Chatflow（对话流）** | 对话式流程构建；Agent 模式通过 `run_query` 运行 `ai_reply` 节点 |
| **Agents（智能体）** | 注册与配置 Agent |
| **Approvals（人工审批）** | HITL gate — 批准/拒绝/编辑计划 JSON |
| **Blackboard（黑板）** | 实时查看共享键 |
| **Analytics（执行分析）** | 执行指标、成功率 |
| **Tracer（任务追踪）** | 实时 WebSocket 追踪（`intent_id`、`trace_id`） |
| **Replay（执行回放）** | 按 `intent_id` 审计与检查点回放 |
| **Events（事件）** | 事件总线历史 |
| **Knowledge Base（知识库）** | RAG 文档管理 |
| **LLM Config（LLM 配置）** | Provider 密钥与路由 |
| **Capability Market（能力市场）** | MCP 插件安装/卸载 |
| **Triggers（触发器）** | 定时与 Webhook 触发 |
| **Variables（变量）** | 环境与工作流变量 |
| **Prompt Templates（Prompt 模板）** | 可复用 Prompt 库 |
| **A/B Testing（A/B 测试）** | 对比 Prompt/模型变体 |
| **Audit Log（审计日志）** | 合规轨迹 |
| **Settings（设置）** | Studio 配置 |

## 5.4 主要 HTTP API

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/agent/query` | POST | NL 查询 → 规划 → 执行 |
| `/api/agent/plan-only` | POST | 仅生成计划 JSON |
| `/api/agent/execute-plan` | POST | 执行已有计划图 |
| `/api/agent/export-langgraph` | POST | 画布导出 LangGraph |
| `/api/workflows/*` | * | Core DAG CRUD + 执行 |
| `/api/hitl/*` | * | 审批门 |
| `/api/blackboard/*` | * | 读写共享状态 |
| `/api/analytics/*` | * | 指标（真实模式） |
| `/api/replay/*` | * | 检查点回放 |

完整参考：[API 手册](../api-reference.md)。

## 5.5 环境变量

| 变量 | 效果 |
|------|------|
| `HIVEFLOW_RUNTIME=agent` | 默认 Agent 运行时 |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | Mock LLM（无需 API Key） |
| `HIVEFLOW_PLAN_HITL=true` | 执行前计划审批 |
| `HIVEFLOW_LLM_PLANNING_PROVIDER` | 规划阶段 LLM 路由 |
| `HIVEFLOW_LLM_EXECUTION_PROVIDER` | 执行阶段 LLM 路由 |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | 真实 LLM Provider |

## 5.6 Chatflow vs Orchestrator

| 特性 | Orchestrator | Chatflow |
|------|--------------|----------|
| 布局 | 自由 DAG 画布 | 对话导向图 |
| 适合 | 批处理流水线、ETL、多步任务 | 聊天机器人、问答流 |
| Agent 模式 | plan-only → 画布 → execute | 拓扑排序的 `ai_reply` 节点 |

## 5.7 Studio 排障

| 现象 | 处理 |
|------|------|
| plan-only 后画布空白 | 查浏览器控制台；确认 `/api/agent/plan-only` 返回 200 |
| 执行无反应 | 确认已开启 **Agent / real mode** |
| 无 LLM 响应 | 设置 `HIVEFLOW_AGENT_ECHO_LLM=true` 或配置 API Key |
| Tracer WS 断开 | 确认后端 :8000；检查 CORS/代理 |
| Approvals 为空 | 启用 `HIVEFLOW_PLAN_HITL=true` 并先运行 plan-only |

见 [Studio Agent 运维](../studio-agent-ops.md)。

## 5.8 练习

1. 用自定义目标完成 Golden Path 并导出 LangGraph JSON。
2. 在 **Approvals** 拒绝计划，编辑 JSON 后重新提交。
3. 执行过程中打开 **Blackboard** 观察键值实时更新。

## 下一步

→ [第 6 部分 — 生产](part-6-production.md)：部署、监控、维护。
