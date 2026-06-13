# Cookbook

Scenario-oriented guides beyond the getting started tutorial. For a **full walkthrough of all 16 examples**, see the [Complete Tutorial](../tutorial/index.md).

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

See [examples/README.md](https://github.com/jdidjhdh/hiveflow/blob/main/examples/README.md) for the full list.
