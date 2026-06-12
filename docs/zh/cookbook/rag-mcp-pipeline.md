# RAG + MCP 流水线

在单一编排工作流中结合检索增强生成与 MCP 工具。

## 适用场景

- 内部知识库 + 实时工具调用（文件系统、API）
- 带文档摄入的 Studio 可视化工作流

## 组件

| 层 | HiveFlow 模块 |
|-------|-----------------|
| 分块与嵌入 | `hiveflow.rag` |
| 工具调用 | `hiveflow.mcp` |
| 编排 | `HiveFlow` + `DAGOrchestrator` |

## 示例

- Core：[examples/06_rag_pipeline.py](https://github.com/jdidjhdh/hiveflow/blob/main/examples/06_rag_pipeline.py)
- MCP：[examples/07_mcp_tools.py](https://github.com/jdidjhdh/hiveflow/blob/main/examples/07_mcp_tools.py)
- 组合 Studio 模板：`packages/studio/examples/rag_pipeline.json`

## 最小 RAG

```python
from hiveflow import RAGPipeline, MemoryVectorStore, DummyEmbeddingModel

store = MemoryVectorStore()
pipeline = RAGPipeline(vector_store=store, embedding_model=DummyEmbeddingModel())
await pipeline.ingest_text("doc-1", "HiveFlow supports HITL and MCP.")
results = await pipeline.query("What supports MCP?")
```

## 添加 MCP 工具

```python
from hiveflow import MCPPluginManager

mgr = MCPPluginManager()
await mgr.register_plugin(
    plugin_id="filesystem",
    name="Filesystem",
    transport="stdio",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
)
```

## 相关

- [OpenAI 集成](../integrations/openai.md)
- [示例 06](https://github.com/jdidjhdh/hiveflow/blob/main/examples/06_rag_pipeline.py)
