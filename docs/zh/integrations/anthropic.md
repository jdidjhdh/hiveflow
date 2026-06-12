# Anthropic 集成

通过与 OpenAI 相同的 `LLMClient` 接口使用 Claude 模型。

## 安装

```bash
pip install "hiveflow[llm]"
export ANTHROPIC_API_KEY=sk-ant-...
```

## Core

```python
from hiveflow import AnthropicClient, LLMMessage

client = AnthropicClient(model="claude-3-5-sonnet-20241022")
response = await client.chat(
    messages=[LLMMessage(role="user", content="Plan a 3-step research workflow.")],
)
```

## Agent 运行时

与 `OpenAIClient` 相同，将 `AnthropicClient` 传给 `HiveMindApp`。

## Studio

在 **LLM Config** 中选择 provider **Anthropic** 并输入 API key。

## 说明

- 工具调用遵循与 OpenAI 客户端相同的 `LLMToolDefinition` 结构
- 混合 provider 流水线时，在自定义 handler 中为不同 Agent 注册不同客户端
