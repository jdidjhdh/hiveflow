# Studio Agent 模式

通过 HiveFlow Studio 与 Agent 运行时运行自然语言规划与 DAG 执行。

## 适用场景

- 可视化编排 + 自然语言生成计划（`plan-only`）
- 在 Agent 运行时逐步执行计划图（`execute-plan`）
- 无需先构建工作流的即席查询（`query`）

## 前置条件

```bash
# Backend (from repo root)
cd packages/studio/backend
pip install -r requirements.txt

export HIVEFLOW_RUNTIME=agent
export HIVEFLOW_AGENT_ECHO_LLM=true   # CI / local UI without API keys
export HIVEFLOW_PLAN_HITL=true        # optional: plan approval gate
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend
cd packages/studio/frontend
npm install && npm run dev
```

打开 **Orchestrator**，启用 **Agent / real mode**，然后使用 Agent 抽屉。

## 三个 HTTP API

| 端点 | 用途 | 返回 |
|----------|---------|---------|
| `POST /api/agent/query` | 完整 NL 查询 → 计划（若启用则 HITL）→ 执行 | `intent_id`、plan、results |
| `POST /api/agent/plan-only` | 仅生成计划 JSON（不执行） | `plan`、`intent_id` |
| `POST /api/agent/execute-plan` | 执行已有计划图 | 各步结果 |

### plan-only → 画布 → execute-plan

1. 用目标调用 **plan-only**。
2. 在 Orchestrator 抽屉中点击 **导入到画布**。
3. 点击 **执行 DAG** — Agent 模式下调用 **execute-plan**，而非 Core `/api/workflows/execute`。

### 导出到 LangGraph

- **Agent 抽屉**（plan-only / run_query 后）：**导出 LangGraph JSON** 或 **导出 LangGraph + Python 模板**
- **工具栏**：**导出 LangGraph** 通过 `POST /api/agent/export-langgraph` 将当前画布 TaskGraph 转换

### Chatflow

Agent 模式下，**Chatflow** 对节点拓扑排序，并通过 `run_query` 逐节点运行 `ai_reply` 步骤（见 `src/utils/chatflowTopology.ts`）。

## 环境变量

| 变量 | 效果 |
|----------|--------|
| `HIVEFLOW_RUNTIME=agent` | 启动时 Agent 运行时已激活 |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | 用于计划的 Mock LLM（CI 友好） |
| `HIVEFLOW_PLAN_HITL=true` | 计划审批暂停（`node_id=plan_approval`） |

## 故障排查

见 [Studio Agent 运维](../studio-agent-ops.md)。

## 相关

- [HITL 审批](hitl-approval.md)
- [快速入门](../getting-started.md#studio-agent-mode)
