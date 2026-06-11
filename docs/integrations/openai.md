# OpenAI Integration

HiveFlow integrates with OpenAI via optional extras and the shared `LLMClient` abstraction.

## Install

```bash
pip install "hiveflow[llm]"
export OPENAI_API_KEY=sk-...
```

## Core: OpenAIClient

```python
from hiveflow import OpenAIClient, LLMMessage

client = OpenAIClient(model="gpt-4o-mini", api_key=os.environ["OPENAI_API_KEY"])

response = await client.chat(
    messages=[LLMMessage(role="user", content="Summarize multi-agent orchestration in one sentence.")],
)
print(response.content)
```

## Agent runtime

The Agent package uses the same client for ReAct workers:

```python
from hiveflow import OpenAIClient
from app import HiveMindApp  # packages/agent

app = HiveMindApp(llm_client=OpenAIClient(model="gpt-4o-mini"))
result = await app.run_query("What is on the blackboard?")
```

## Studio

1. Open **Settings → LLM Config**
2. Provider: **OpenAI**
3. Set API key (stored in Studio credentials store, not in repo)
4. Run workflows from **Orchestrator** in real mode (toggle off mock)

## Environment variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | API authentication |
| `OPENAI_BASE_URL` | Optional proxy / Azure-compatible endpoint |

## Multimodal (optional)

```bash
pip install "hiveflow[all]"
```

Use `OpenAIImageProcessor`, `OpenAIAudioProcessor`, and `OpenAIVideoProcessor` from `hiveflow.multimodal` — see [example 15](https://github.com/hiveflow/hiveflow/blob/main/examples/15_multimodal_pipeline.py).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ImportError: openai` | `pip install "hiveflow[llm]"` |
| 401 Unauthorized | Check `OPENAI_API_KEY` |
| Rate limits | Lower concurrency in scheduler or add retries in custom handler |
