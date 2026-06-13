# Cookbook

面向场景的指南，超出快速入门教程的范围。如需 **16 个示例的完整逐步教程**，请参阅 [完整教程](../tutorial/index.md)。

| 场景 | 指南 |
|----------|-------|
| 副作用前的人工审批 | [HITL 审批流程](hitl-approval.md) |
| 多专家 + 综合器 | [多智能体辩论](multi-agent-debate.md) |
| 知识库 + MCP 工具 | [RAG + MCP 流水线](rag-mcp-pipeline.md) |
| Studio Agent 模式（query / plan / execute） | [Studio Agent 模式](studio-agent-mode.md) |
| Checkpoint 恢复与回放 | [Checkpoint 恢复](checkpoint-recovery.md) |
| LangGraph 运行时 + HiveFlow HITL/审计 | [LangGraph Sidecar](langgraph-sidecar.md) |

## 可运行示例

所有示例在 CI 中做冒烟测试：

```bash
pip install -e "packages/core[all]"
python examples/run_smoke_tests.py
```

完整列表见 [examples/README.md](https://github.com/jdidjhdh/hiveflow/blob/main/examples/README.md)。
