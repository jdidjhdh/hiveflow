# HiveFlow Core

[English](README.md) · **简体中文**

**PyPI：** [`hiveflow`](https://pypi.org/project/hiveflow/) · **路径：** `packages/core`

HiveFlow 的可嵌入编排内核。Core 提供在 Python 中构建多智能体系统所需的基础原语，不依赖 UI 或 LLM——你提供任务处理器，Core 负责调度、共享状态与工作流结构。

## 功能概览

| 领域 | 组件 |
|------|------|
| **消息传递** | `ECM`（Event-Condition-Messaging），进程内或 Redis 事件总线 |
| **Worker** | `Cell` 监督树、基于技能的 `Scheduler`（最少负载 / 拍卖 / 负载感知） |
| **共享状态** | `SecureBlackboard` — 内存、TTL、Redis 或加密后端，并支持审计 |
| **工作流** | `DAGOrchestrator`、`DynamicOrchestrator`、检查点 / 时间旅行 |
| **安全与合规** | `HITLManager`、输入/输出 `Guards`、验证流水线 |
| **数据与工具** | RAG 流水线、MCP 插件管理器、评估 / A/B 测试 |
| **可观测性** | 指标采集器、可选 OpenTelemetry 追踪 |

## 何时使用 Core

- 在你自己的服务或框架中嵌入编排能力
- 需要对智能体、黑板键与调度策略拥有完全控制权
- 构建自定义 HITL 或 DAG 逻辑，无需 Studio 或自然语言规划
- 以最小依赖（`pip install hiveflow`）交付，不引入 Agent/LLM 栈

如需自然语言规划与 Skill 图，请添加 [`hiveflow-agent`](../agent/README.md)。如需可视化运维 UI，请使用 [Studio](../studio/README.md)。

## 安装

```bash
pip install hiveflow
pip install "hiveflow[security]"   # encryption + JSON schema
pip install "hiveflow[llm]"        # OpenAI + Anthropic clients
pip install "hiveflow[rag]"        # RAG utilities
pip install "hiveflow[all]"        # all optional extras
```

从源码安装：

```bash
cd packages/core && pip install -e ".[dev]"
```

## 快速开始

注册带任务处理器的智能体，通过 `ECM` 消息调度工作，并从共享黑板读取结果：

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
            intent="Say hello",
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

可运行示例：[`examples/01_hello_hiveflow.py`](../../examples/01_hello_hiveflow.py)

## 开发

```bash
cd packages/core
pip install -e ".[dev]"
pytest --cov=hiveflow --cov-fail-under=60
ruff check hiveflow/
mypy
```

## 质量（0.1.x Alpha）

| 门禁 | 目标 |
|------|------|
| PyPI 分类器 | `Development Status :: 3 - Alpha` — 0.1.x 有意为之 |
| 测试覆盖率 | **≥ 60%**（`hiveflow/`，CI 强制） |
| MyPy | `pyproject.toml` 中列出的公开模块 |

RAG、multimodal、完整 `llm_client` 类型检查不在 0.1.x 范围内。详见 [质量门禁](https://jdidjhdh.github.io/hiveflow/zh/quality-gates/)。

## 文档

- [Getting Started](https://jdidjhdh.github.io/hiveflow/getting-started/)
- [API Reference](https://jdidjhdh.github.io/hiveflow/api/)
- [Architecture — Layer 1](https://jdidjhdh.github.io/hiveflow/architecture/)
- [Main repository README](../../README.md)

## 许可证

MIT — 与 HiveFlow 项目根目录相同。
