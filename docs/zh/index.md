# HiveFlow 文档

<p align="center">
  <img src="../assets/logo.svg" alt="HiveFlow" width="72"/>
</p>

**HiveFlow** 是开源的**多 Agent 协调与 HITL 层**，附带可视化 **Studio** 与原生 **MCP** 工具集成。

> **状态：0.1.x Alpha** — API 可能演进；请参阅 [版本策略](versioning.md)。

## 选择你的路径

| 我想要… | 从这里开始 |
|------------|------------|
| 在 Python 中嵌入编排能力 | [Core 模块](modules/index.md#core--orchestration-kernel) · [快速入门](getting-started.md) |
| 自然语言规划 + Agent 运行时 | [Agent 模块](modules/index.md#agent--cognitive-runtime) · [Studio Agent 指南](cookbook/studio-agent-mode.md) |
| 可视化工作流 + 运维 UI | [Studio 模块](modules/index.md#studio--visual-operations-platform) · [Agent 运维](studio-agent-ops.md) |
| 从 LangGraph 迁移 | [迁移指南](guides/migrate-from-langgraph.md) · [LangGraph Sidecar](cookbook/langgraph-sidecar.md) |

## 三大模块

| 模块 | 说明 | 详情 |
|--------|-------------|---------|
| **Core** (`hiveflow`) | 调度器、黑板、DAG/HITL/RAG/MCP 内核 | [模块概览](modules/index.md#core--orchestration-kernel) |
| **Agent** (`hiveflow-agent`) | 自然语言 TaskGraph 规划 + 认知执行 | [模块概览](modules/index.md#agent--cognitive-runtime) |
| **Studio** | 自托管 FastAPI + React 运维 UI | [模块概览](modules/index.md#studio--visual-operations-platform) |

## 快速链接

- [快速入门](getting-started.md) — 安装与第一个工作流
- [核心概念](concepts.md) — ECM、Cell、Blackboard、Scheduler
- [Cookbook](cookbook/index.md) — HITL、RAG、Studio Agent 模式
- [API 参考](api/index.md) — 自动生成的 Core API
- [架构](architecture.md) — 三层设计
- [部署](deployment.md) — Docker、Kubernetes
- [可观测性](observability.md) — 指标、追踪、Studio 分析

## 最小示例（Core）

```python
import asyncio
from hiveflow import HiveFlow, HiveFlowConfig, ECM

async def main():
    hf = HiveFlow(HiveFlowConfig())
    await hf.start()
    try:
        async def handler(ecm, view):
            await view.put("result", f"Done: {ecm.intent}")
        await hf.create_agent("worker", {"process"}, set(), {"result"}, handler)
        await hf.scheduler.schedule(ECM(
            trace_id="1", intent="Hello", intent_id="1",
            emitter="user", required_skills=["process"],
        ))
    finally:
        await hf.shutdown()

asyncio.run(main())
```

## 社区

- [GitHub 仓库](https://github.com/hiveflow/hiveflow)
- [Issue 跟踪](https://github.com/hiveflow/hiveflow/issues)
- [Discussions](https://github.com/hiveflow/hiveflow/discussions)（需在仓库设置中启用）
- [贡献指南](https://github.com/hiveflow/hiveflow/blob/main/CONTRIBUTING.md)
- [治理](https://github.com/hiveflow/hiveflow/blob/main/GOVERNANCE.md)
