# HiveFlow Agent Runtime

[English](README.md) · **简体中文**

**PyPI：** [`hiveflow-agent`](https://pypi.org/project/hiveflow-agent/) · **路径：** `packages/agent` · **依赖：** `hiveflow>=0.1`

认知运行时层。Agent 基于 [Core](../core/README.md) 构建，新增自然语言意图解析、动态 TaskGraph 规划、ReAct Worker、记忆、护栏与 MCP 技能注册——主要通过 `HiveMindApp` 对外暴露。

## 功能概览

| 领域 | 组件 |
|------|------|
| **入口** | `HiveMindApp` / `HiveMindConfig` — 连接 Core、LLM、记忆与编排器 |
| **规划** | `CognitiveOrchestrator` — LLM 生成 TaskGraph，失败时可重新规划 |
| **执行** | Skill 绑定 → ReAct Worker；通过 Core 调度器调度 ECM 任务 |
| **记忆** | 短期上下文 + 长期向量召回 |
| **安全** | 输入护栏、输出验证器（可选） |
| **MCP** | 将插件工具注册为 Skill（`mcp_*`） |
| **HITL** | 可选的计划审批门控（`enable_plan_hitl`），在图执行前生效 |

## 核心 API

| 方法 | 用途 |
|------|------|
| `run_query(user_input)` | 解析意图 → 规划 →（可选 HITL）→ 执行 → 返回答案 |
| `plan_only(user_input)` | 仅返回 TaskGraph JSON，不执行 |
| `execute_plan(graph_spec, query)` | 运行预先构建的计划（例如来自 Studio 画布或 LangGraph 导入） |

Studio 通过 HTTP 暴露相同接口：`/api/agent/query`、`/api/agent/plan-only`、`/api/agent/execute-plan`。

## 何时使用 Agent

- 用户用自然语言描述任务，而非手写 DAG
- 需要自动生成 Skill 图与重新规划能力
- 与 Studio Agent 模式集成，或在你自己的 FastAPI/CLI 应用中调用 `HiveMindApp`
- 已在使用 Core，需要更高层的编排门面

若仅需底层 ECM/调度，单独使用 [Core](../core/README.md) 即可。如需可视化 HITL 与分析，请添加 [Studio](../studio/README.md)。

## 安装

```bash
pip install hiveflow-agent
```

从源码安装（monorepo）：

```bash
cd packages/agent
pip install -r requirements.txt   # includes editable ../core
pip install pytest pytest-asyncio pytest-timeout
```

## 快速开始

```python
import asyncio
from hiveflow import HiveFlowConfig, MockLLMClient
from app import HiveMindApp, HiveMindConfig
from memory.vector_store import InMemoryVectorStore


async def main():
    llm = MockLLMClient(response='{"research":{"task":"search","depends_on":[]},"final_answer":{"task":"summarize","depends_on":["research"]}}')
    config = HiveMindConfig(
        hiveflow_config=HiveFlowConfig(),
        llm=llm,
        embedding_llm=llm,
        vector_store=InMemoryVectorStore(),
        skill_registry={"search": "searcher", "summarize": "writer"},
    )
    app = HiveMindApp(config)
    await app.start()
    try:
        result = await app.run_query("Summarize latest AI news")
        print(result)
    finally:
        await app.shutdown()


asyncio.run(main())
```

另见：[`examples/08_cognitive_planning.py`](../../examples/08_cognitive_planning.py)、[`examples/16_langgraph_export.py`](../../examples/16_langgraph_export.py)。

## 环境变量（Studio / 本地）

| 变量 | 作用 |
|------|------|
| `HIVEFLOW_RUNTIME=agent` | 在 Studio 后端启用 Agent 模式 |
| `HIVEFLOW_AGENT_ECHO_LLM=true` | 用于 CI / UI 开发的 Mock LLM，无需 API 密钥 |
| `HIVEFLOW_PLAN_HITL=true` | 执行前需人工审批计划 |

## 开发

```bash
cd packages/agent
pytest tests/ \
  --ignore=tests/test_real_llm.py \
  --ignore=tests/test_llm_connection.py \
  --cov --cov-fail-under=60
```

### 可选：真实 LLM 集成测试

CI 不运行（非确定性；需 API 密钥或本地 Ollama）：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=...
pytest tests/test_real_llm.py -v -m real_llm
```

**发版耦合：** 同一 git tag 同时发布 `hiveflow` 与 `hiveflow-agent`。见 [质量门禁](https://hiveflow.github.io/hiveflow/zh/quality-gates/)。

## 文档

- [Studio Agent cookbook](https://hiveflow.github.io/hiveflow/cookbook/studio-agent-mode/)
- [Studio Agent ops](https://hiveflow.github.io/hiveflow/studio-agent-ops/)
- [Architecture — Layer 2](https://hiveflow.github.io/hiveflow/architecture/)
- [Main repository README](../../README.md)

## 许可证

MIT — 与 HiveFlow 项目根目录相同。
