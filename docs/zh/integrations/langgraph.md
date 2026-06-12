# LangGraph 集成（PoC）

**状态：实验性（v0.3 预览）** — 将 HiveFlow TaskGraph 计划与 LangGraph 导向的 JSON 规格互转。不在 HiveFlow 内执行 LangGraph 图。

## 安装

```bash
pip install hiveflow
# Optional, to run generated code:
pip install langgraph langchain-core
```

## 导出 HiveFlow 计划 → LangGraph 规格

`plan-only` 或认知规划后，你会收到 TaskGraph JSON：

```python
plan = {
    "research": {"task": "search", "depends_on": []},
    "draft": {"task": "write", "depends_on": ["research"]},
    "final_answer": {"task": "summarize", "depends_on": ["draft"]},
}
```

转换：

```python
from hiveflow.adapters.langgraph import taskgraph_to_langgraph, dumps_langgraph_spec

spec = taskgraph_to_langgraph(plan, workflow_id="content_pipeline")
print(dumps_langgraph_spec(spec))
```

输出包含：

- `nodes[]`，含 `id` 与 `action`（HiveFlow skill 名）
- `edges[]`，含 `__start__` / `__end__`
- `interrupt_before[]` — 来自带 `hitl` 配置的节点

## 导入 LangGraph 规格 → HiveFlow 计划

```python
from hiveflow.adapters.langgraph import langgraph_to_taskgraph

plan = langgraph_to_taskgraph(spec)
# Execute via POST /api/agent/execute-plan or CognitiveOrchestrator.execute_plan
```

## 生成 LangGraph Python（示意）

```python
from hiveflow.adapters.langgraph import render_langgraph_python

code = render_langgraph_python(spec, graph_name="content_graph")
Path("exported_graph.py").write_text(code)
```

生成的代码是**起点** — 生产 LangGraph HITL 需接入真实工具与 checkpointer。

## Studio 工作流

1. Orchestrator → Agent 模式 → **plan-only**
2. 从抽屉导出计划 JSON（**导出 LangGraph JSON**）或通过 API
3. `taskgraph_to_langgraph(plan)` → 与 LangGraph 团队共享或运行 codegen
4. 往返：`langgraph_to_taskgraph(spec)` → **导入到画布** → **execute-plan**

工具栏 **导出 LangGraph** 可在无 Agent plan 步骤时导出当前画布图。

## 限制（PoC）

| 功能 | 支持 |
|---------|-----------|
| Skill 拓扑 / depends_on | ✅ |
| HITL → interrupt_before 提示 | ✅ |
| Checkpoint 元数据 | ❌（导出时丢失） |
| 条件边 | ❌ |
| Core 内实时 LangGraph 执行 | ❌ |
| LangChain Tool 桥接 | 规划中 |

## 测试

```bash
cd packages/core && pytest tests/test_langgraph_adapter.py -v
```

## 另见

- [LangGraph + HiveFlow Sidecar 指南](../cookbook/langgraph-sidecar.md) — 外部运行 LangGraph，HITL/审计在 HiveFlow
- [从 LangGraph 迁移](../guides/migrate-from-langgraph.md)
- [Studio Agent 模式指南](../cookbook/studio-agent-mode.md)
