# Integrations

HiveFlow connects to external systems through optional dependency groups and Studio configuration.

| Integration | Package extra | Doc |
|-------------|---------------|-----|
| OpenAI | `hiveflow[llm]` | [OpenAI](openai.md) |
| Anthropic | `hiveflow[llm]` | [Anthropic](anthropic.md) |
| Redis (bus / blackboard) | `hiveflow[redis]` | [Redis](redis.md) |
| PostgreSQL (Studio) | Studio backend deps | [PostgreSQL](postgres.md) |
| LangGraph (plan export/import) | Core adapter (no extra) | [LangGraph PoC](langgraph.md) |

## Optional dependency groups

```bash
pip install "hiveflow[security]"   # cryptography, jsonschema
pip install "hiveflow[redis]"      # redis
pip install "hiveflow[llm]"        # openai, anthropic
pip install "hiveflow[rag]"        # numpy, scikit-learn
pip install "hiveflow[all]"        # everything above
```

## Contributing a new integration

1. Implement against existing abstractions (`LLMClient`, `BlackboardBackend`, `EventBus`, `MCPPluginManager`)
2. Add optional dependency in `packages/core/pyproject.toml`
3. Add a page under `docs/integrations/` and link from this index
4. Add an example under `examples/` and register in `run_smoke_tests.py`

See [CONTRIBUTING.md](https://github.com/jdidjhdh/hiveflow/blob/main/CONTRIBUTING.md) for PR requirements.
