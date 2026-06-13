# 第 4 部分 — 集成

多模态处理与 LangGraph 互操作。

## 4.1 多模态流水线（示例 15）

在统一流水线中处理图像、音频、视频（示例使用 mock Provider；生产环境替换为真实 API）。

```bash
python examples/15_multimodal_pipeline.py
```

典型输出：

| 模态 | 字段 |
|------|------|
| 图像 | `description`、`labels`、`confidence` |
| 音频 | `text`（转录）、`language` |
| 视频 | `summary`、`key_frames`、`scenes` |

在 `hiveflow.multimodal` 中实现适配器接口以接入真实 Provider。

## 4.2 LangGraph 导出（示例 16）

将 HiveFlow TaskGraph 导出为 LangGraph 兼容 JSON 与 Python 脚手架。

```bash
python examples/16_langgraph_export.py
```

导出内容包括：

- `state_schema`（messages、results、intent_id）
- 带 action/skill 的 `nodes`
- 含 `__start__` / `__end__` 的 `edges`
- HITL 节点的可选 `interrupt_before`

生成的 Python 依赖 `langgraph` + `langchain-core`（PoC — 见版本策略）。

### Sidecar 模式

LangGraph 作为 **执行运行时**，HiveFlow 作为 **协调层**（HITL、审计、黑板、Studio UI）：

```
用户 → Studio → HiveFlow（HITL + 审计 + 黑板）
                      ↓
               LangGraph 运行时（图执行）
```

深度阅读：[LangGraph Sidecar Cookbook](../cookbook/langgraph-sidecar.md)、[LangGraph 集成](../integrations/langgraph.md)。

### Studio 导出按钮

在 **Orchestrator（编排器）** Agent 模式下：

1. **plan-only** → **导出 LangGraph JSON** 或 **导出 LangGraph + Python 模板**
2. 工具栏 **导出 LangGraph** — 通过 `POST /api/agent/export-langgraph` 转换当前画布

## 4.3 LLM Provider 集成

| Provider | 文档 | 环境变量 |
|----------|------|----------|
| OpenAI | [integrations/openai.md](../integrations/openai.md) | `OPENAI_API_KEY` |
| Anthropic | [integrations/anthropic.md](../integrations/anthropic.md) | `ANTHROPIC_API_KEY` |
| Ollama | Agent `llm/ollama_client.py` | `OLLAMA_BASE_URL` |
| DeepSeek | Agent `llm/deepseek_client.py` | `DEEPSEEK_API_KEY` |

规划与执行可分别路由：

```bash
HIVEFLOW_LLM_PLANNING_PROVIDER=openai
HIVEFLOW_LLM_EXECUTION_PROVIDER=anthropic
```

## 4.4 MCP 生态

HiveFlow 原生支持 MCP（`hiveflow.mcp`）。插件注册的工具可被任何 MCP 兼容 Agent 发现。见 [第 2 部分 — MCP](part-2-workflows.md#26-mcp-示例-07)。

## 4.5 练习

1. 将示例 02 的流水线导出为 LangGraph JSON 并检查 node ID。
2. 在示例 15 中用真实视觉 API 替换 mock 图像分析。
3. 在 `HIVEFLOW_PLAN_HITL=true` 下运行 LangGraph sidecar，并在 Studio 审批计划。

## 下一步

→ [第 5 部分 — Studio](part-5-studio.md)：完整可视化运维 UI  walkthrough。
