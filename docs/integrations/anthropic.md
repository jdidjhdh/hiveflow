# Anthropic Integration

Use Claude models through the same `LLMClient` interface as OpenAI.

## Install

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

## Agent runtime

Pass `AnthropicClient` to `HiveMindApp` the same way as `OpenAIClient`.

## Studio

In **LLM Config**, select provider **Anthropic** and enter the API key.

## Notes

- Tool calling follows the same `LLMToolDefinition` shape as OpenAI client
- For mixed-provider pipelines, register different agents with different clients in custom handlers
