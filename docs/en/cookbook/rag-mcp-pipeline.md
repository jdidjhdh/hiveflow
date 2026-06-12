# RAG + MCP Pipeline

Combine retrieval-augmented generation with MCP tools in one orchestrated workflow.

## When to use

- Internal knowledge bases + live tool calls (filesystem, APIs)
- Studio visual workflows with document ingestion

## Components

| Layer | HiveFlow module |
|-------|-----------------|
| Chunk & embed | `hiveflow.rag` |
| Tool calls | `hiveflow.mcp` |
| Orchestration | `HiveFlow` + `DAGOrchestrator` |

## Examples

- Core: [examples/06_rag_pipeline.py](https://github.com/hiveflow/hiveflow/blob/main/examples/06_rag_pipeline.py)
- MCP: [examples/07_mcp_tools.py](https://github.com/hiveflow/hiveflow/blob/main/examples/07_mcp_tools.py)
- Combined Studio template: `packages/studio/examples/rag_pipeline.json`

## Minimal RAG

```python
from hiveflow import RAGPipeline, MemoryVectorStore, DummyEmbeddingModel

store = MemoryVectorStore()
pipeline = RAGPipeline(vector_store=store, embedding_model=DummyEmbeddingModel())
await pipeline.ingest_text("doc-1", "HiveFlow supports HITL and MCP.")
results = await pipeline.query("What supports MCP?")
```

## Add MCP tools

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

## Related

- [OpenAI integration](../integrations/openai.md)
- [example 06](https://github.com/hiveflow/hiveflow/blob/main/examples/06_rag_pipeline.py)
