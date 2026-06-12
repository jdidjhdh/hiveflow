# Cookbook

Scenario-oriented guides beyond the getting started tutorial.

| Scenario | Guide |
|----------|-------|
| Human approval before side effects | [HITL approval flow](hitl-approval.md) |
| Multiple specialists + synthesizer | [Multi-agent debate](multi-agent-debate.md) |
| Knowledge base + MCP tools | [RAG + MCP pipeline](rag-mcp-pipeline.md) |
| Studio Agent mode (query / plan / execute) | [Studio Agent mode](studio-agent-mode.md) |
| Checkpoint restore & replay | [Checkpoint recovery](checkpoint-recovery.md) |
| LangGraph runtime + HiveFlow HITL/audit | [LangGraph Sidecar](langgraph-sidecar.md) |

## Runnable examples

All examples are smoke-tested in CI:

```bash
pip install -e "packages/core[all]"
python examples/run_smoke_tests.py
```

See [examples/README.md](https://github.com/hiveflow/hiveflow/blob/main/examples/README.md) for the full list.
