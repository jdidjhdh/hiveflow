# OpenAI 集成

HiveFlow 通过可选 extra 与共享 `LLMClient` 抽象集成 OpenAI。

## 安装

```bash
pip install "hiveflow[llm]"
export OPENAI_API_KEY=sk-...
```

## Core：OpenAIClient

```python
from hiveflow import OpenAIClient, LLMMessage

client = OpenAIClient(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])

response = await client.chat(
    messages=[LLMMessage(role="user", content="Summarize multi-agent orchestration in one sentence.")],
)
print(response.content)
```

## Agent 运行时

Agent 包为 ReAct Worker 使用同一客户端：

```python
from hiveflow import OpenAIClient
from app import HiveMindApp  # packages/agent

app = HiveMindApp(llm_client=OpenAIClient(model="gpt-4o-mini"))
result = await app.run_query("What is on the blackboard?")
```

## Studio

1. 打开 **Settings → LLM Config**
2. Provider：**OpenAI**
3. 设置 API key（存储在 Studio 凭据库，不在仓库中）
4. 在 **Orchestrator** 中以真实模式运行工作流（关闭 mock）

## 环境变量

| 变量 | 用途 |
|----------|---------|
| `OPENAI_API_KEY` | API 认证 |
| `OPENAI_BASE_URL` | 可选代理 / Azure 兼容端点 |

## 多模态（可选）

```bash
pip install "hiveflow[all]"
```

从 `hiveflow.multimodal` 使用 `OpenAIImageProcessor`、`OpenAIAudioProcessor`、`OpenAIVideoProcessor` — 见 [示例 15](https://github.com/jdidjhdh/hiveflow/blob/main/examples/15_multimodal_pipeline.py)。

## 故障排查

| 问题 | 处理 |
|-------|-----|
| `ImportError: openai` | `pip install "hiveflow[llm]"` |
| 401 Unauthorized | 检查 `OPENAI_API_KEY` |
| Rate limits | 降低调度器并发或在自定义 handler 中添加重试 |
