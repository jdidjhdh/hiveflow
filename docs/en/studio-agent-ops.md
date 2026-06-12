# Studio Agent 运维指南

## 快速检查清单

1. 后端健康：`GET /api/health` → `{"status":"ok","running":true}`
2. 运行时：`GET /api/agent/runtime` → `runtime_mode: agent`, `agent_active: true`
3. Skills 列表：`skills` 数组含 `general`、`summarize` 及 `mcp_*`（安装 MCP 插件后）

## 常见问题

### 503 Agent runtime is not active

**原因**：当前为 Core 模式或未调用 `POST /api/agent/runtime` 切换。

**处理**：

- 设置 `HIVEFLOW_RUNTIME=agent` 并重启后端，或
- Studio 编排器打开 Agent 开关，或
- `POST /api/agent/runtime` body: `{"mode":"agent"}`

### 人工审批页无 pending 项

**原因**：未开启计划 HITL，或 query 尚未触发规划门。

**处理**：

- 设置 `HIVEFLOW_PLAN_HITL=true` 并重启 Agent 运行时
- 在 Agent 模式下执行 `run_query`（非 plan-only）
- 刷新「人工审批」或等待 WS `hitl.pending` 事件

### Echo LLM / 无 API Key 联调

设置 `HIVEFLOW_AGENT_ECHO_LLM=true`。Echo 会返回固定 JSON 计划，适合 CI 与本地 UI 联调，无需 OpenAI/Anthropic。

### Analytics 仍显示 Mock 数据

确认 Studio 顶栏为**真实模式**（非 mock）。真实模式会请求 `/api/analytics/*` 与 `/api/metrics`。

### intent_id 查不到 Replay 记录

Replay 依赖黑板 audit。执行 Agent query 后，在「执行回放」输入返回的 `intent_id`，或从编排器结果链接跳转。

## Docker Compose

```bash
docker compose up studio frontend
```

`studio` 服务默认启用 `HIVEFLOW_RUNTIME=agent`、`HIVEFLOW_PLAN_HITL=true`、`HIVEFLOW_AGENT_ECHO_LLM=true`。

## 测试命令

```powershell
cd packages/studio/backend
$env:HIVEFLOW_AGENT_ECHO_LLM="true"
python -m pytest tests/test_agent_api.py tests/test_analytics_api.py -q
```
