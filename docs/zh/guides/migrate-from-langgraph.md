# 从 LangGraph 迁移

LangGraph 与 HiveFlow 之间的概念映射。HiveFlow 面向需要开箱即用 **HITL**、**Studio UI** 与**安全共享状态**的团队。

## 概念对照

| LangGraph | HiveFlow | 说明 |
|-----------|----------|-------|
| `StateGraph` | `DAGOrchestrator` / `CognitiveOrchestrator` | 静态 vs 运行时生成计划 |
| Graph nodes | Agents + `task_handler` | 基于 Skill 的调度 |
| Shared state | `SecureBlackboard` | 加密 + 审计键 |
| `interrupt()` / human node | `HITLManager` + `HITLAction` | 原生 gate + Studio Approvals |
| Checkpointer | `CheckpointManager` | Blackboard 快照 |
| Tool calling | MCP + `ReActWorker` | MCP 优先的插件模型 |
| LangSmith traces | Studio Tracer / Replay | `trace_id` ↔ `intent_id` |

## 典型迁移路径

### 1. 固定 DAG → Core 编排器

用 HiveFlow 任务图或 Studio Orchestrator 画布替换 LangGraph 边，然后通过 Core 调度器或 `/api/workflows/execute` 执行。

### 2. 动态 Agent → Agent 运行时

将 `create_react_agent` 循环替换为：

```python
from app import HiveMindApp, HiveMindConfig  # hiveflow-agent

result = await app.run_query("Summarize the quarterly report")
```

Studio 等价操作：`POST /api/agent/query`。

### 3. 人工审批

LangGraph `interrupt_before` → HiveFlow：

```python
gate = await hitl.create_gate(
    workflow_id="wf-1",
    node_id="publish",
    action=HITLAction.APPROVAL,
    prompt="Approve before publish",
    context={"draft": "..."},
)
```

见 [HITL 指南](../cookbook/hitl-approval.md)。

## 尚非 1:1 的能力

- **LangGraph 适配器** — PoC 可用：[LangGraph 集成](../integrations/langgraph.md)（`taskgraph_to_langgraph` / 往返）。完整运行时桥接计划 v0.3。
- **LangChain Tool 包装器** — 当前使用 MCP 或自定义 `ReActTool`
- **LangSmith 托管评估** — 使用 HiveFlow `Evaluator` + Studio Analytics

## 下一步

- [LangGraph + HiveFlow Sidecar](../cookbook/langgraph-sidecar.md) — 推荐集成模式
- [快速入门](../getting-started.md)
- [Studio Agent 模式](../cookbook/studio-agent-mode.md)
