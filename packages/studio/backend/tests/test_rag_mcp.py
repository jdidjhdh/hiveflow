"""HiveFlow - RAG and MCP Module Tests"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import (
    DocumentProcessor, Document, DocumentType,
    TextChunker, DocumentChunk, ChunkStrategy,
    MemoryVectorStore, SearchResult,
    RAGPipeline, RAGResult, DummyEmbeddingModel,
    KnowledgeBaseManager, KnowledgeBase,
    MCPClient, MCPTool, MCPToolParam, MCPTransportType,
    MCPPluginManager, MCPPlugin, MCPToolCallResult,
)


# ======================== Document Processor Tests ========================

def test_document_processor_parse_text():
    processor = DocumentProcessor()
    doc = processor.parse_text("Hello world", source="test")
    assert doc.content == "Hello world"
    assert doc.doc_type == DocumentType.TEXT
    assert doc.metadata["source"] == "test"


def test_document_processor_parse_markdown():
    processor = DocumentProcessor()
    doc = processor.parse_markdown("# Title\nContent here", source="test.md")
    assert doc.doc_type == DocumentType.MARKDOWN
    assert "# Title" in doc.content


def test_document_processor_parse_html():
    processor = DocumentProcessor()
    doc = processor.parse_html("<p>Hello <b>world</b></p>", source="test.html")
    assert doc.doc_type == DocumentType.HTML
    assert "Hello" in doc.content
    assert "<p>" not in doc.content


def test_document_processor_strip_html():
    processor = DocumentProcessor()
    text = processor._strip_html("<div><script>alert(1)</script>Hello World</div>")
    assert "alert" not in text.lower()
    assert "Hello World" in text


def test_document_processor_compute_doc_id():
    doc_id1 = Document.compute_doc_id("hello", "source1")
    doc_id2 = Document.compute_doc_id("hello", "source1")
    doc_id3 = Document.compute_doc_id("hello", "source2")
    assert doc_id1 == doc_id2
    assert doc_id1 != doc_id3


def test_document_processor_parse_csv():
    processor = DocumentProcessor()
    csv_content = b"name,age\nAlice,30\nBob,25"
    # Create temp file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(csv_content)
        f.flush()
        doc = processor.parse(f.name)

    assert doc.doc_type == DocumentType.CSV
    assert doc.metadata["rows"] == 2
    assert doc.metadata["columns"] == 2


def test_document_processor_parse_json():
    processor = DocumentProcessor()
    import tempfile, json
    data = {"name": "Alice", "age": 30, "tags": ["dev", "ai"]}
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(data, f)
        f.flush()
        doc = processor.parse(f.name)

    assert doc.doc_type == DocumentType.JSON
    assert "name: Alice" in doc.content


def test_document_processor_detect_type():
    processor = DocumentProcessor()
    assert processor._detect_type("file.txt") == DocumentType.TEXT
    assert processor._detect_type("file.md") == DocumentType.MARKDOWN
    assert processor._detect_type("file.html") == DocumentType.HTML
    assert processor._detect_type("file.pdf") == DocumentType.PDF
    assert processor._detect_type("file.csv") == DocumentType.CSV
    assert processor._detect_type("file.json") == DocumentType.JSON
    assert processor._detect_type("file.unknown") == DocumentType.TEXT


# ======================== Text Chunker Tests ========================

def test_chunker_fixed_strategy():
    chunker = TextChunker(strategy=ChunkStrategy.FIXED, chunk_size=10, chunk_overlap=0)
    doc = Document(doc_id="d1", content="A" * 25, doc_type=DocumentType.TEXT)
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 3  # 25/10 = 3 chunks
    assert all(c.doc_id == "d1" for c in chunks)


def test_chunker_fixed_with_overlap():
    chunker = TextChunker(strategy=ChunkStrategy.FIXED, chunk_size=10, chunk_overlap=3)
    doc = Document(doc_id="d1", content="1234567890" * 3, doc_type=DocumentType.TEXT)
    chunks = chunker.chunk(doc)
    assert len(chunks) > 0


def test_chunker_semantic_strategy():
    chunker = TextChunker(strategy=ChunkStrategy.SEMANTIC, chunk_size=100)
    content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    doc = Document(doc_id="d1", content=content, doc_type=DocumentType.TEXT)
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunker_markdown_strategy():
    chunker = TextChunker(strategy=ChunkStrategy.MARKDOWN)
    content = "# Section 1\nContent 1\n\n# Section 2\nContent 2"
    doc = Document(doc_id="d1", content=content, doc_type=DocumentType.MARKDOWN)
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunker_code_strategy():
    chunker = TextChunker(strategy=ChunkStrategy.CODE)
    content = "def foo():\n    pass\n\nclass Bar:\n    pass"
    doc = Document(doc_id="d1", content=content, doc_type=DocumentType.TEXT)
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunker_recursive_strategy():
    chunker = TextChunker(strategy=ChunkStrategy.RECURSIVE, chunk_size=20, chunk_overlap=5)
    content = "First sentence. Second sentence. Third sentence.\n\nNew paragraph here."
    doc = Document(doc_id="d1", content=content, doc_type=DocumentType.TEXT)
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunker_empty_content():
    chunker = TextChunker()
    doc = Document(doc_id="d1", content="", doc_type=DocumentType.TEXT)
    chunks = chunker.chunk(doc)
    assert len(chunks) == 0


def test_chunker_short_content():
    chunker = TextChunker(chunk_size=100)
    doc = Document(doc_id="d1", content="Short text", doc_type=DocumentType.TEXT)
    chunks = chunker.chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].content == "Short text"


# ======================== Vector Store Tests ========================

@pytest.mark.asyncio
async def test_memory_vector_store_add_and_search():
    store = MemoryVectorStore()
    embedding = DummyEmbeddingModel(dim=128)

    chunks = [
        DocumentChunk(chunk_id="c1", doc_id="d1", content="Python is great", index=0),
        DocumentChunk(chunk_id="c2", doc_id="d1", content="Java is also good", index=1),
    ]
    embeddings = await embedding.embed([c.content for c in chunks])

    ids = await store.add(chunks, embeddings)
    assert len(ids) == 2

    query_vec = await embedding.embed_query("Python")
    results = await store.search(query_vec, top_k=1)
    assert len(results) == 1
    # DummyEmbeddingModel uses hash-based vectors, so results are deterministic
    # Just verify we got a result, not which one
    assert results[0].chunk.content in ["Python is great", "Java is also good"]


@pytest.mark.asyncio
async def test_memory_vector_store_delete():
    store = MemoryVectorStore()
    embedding = DummyEmbeddingModel(dim=128)

    chunks = [
        DocumentChunk(chunk_id="c1", doc_id="d1", content="Content A", index=0),
        DocumentChunk(chunk_id="c2", doc_id="d2", content="Content B", index=0),
    ]
    embeddings = await embedding.embed([c.content for c in chunks])
    await store.add(chunks, embeddings)

    assert await store.count() == 2
    deleted = await store.delete("d1")
    assert deleted == 1
    assert await store.count() == 1


@pytest.mark.asyncio
async def test_memory_vector_store_filters():
    store = MemoryVectorStore()
    embedding = DummyEmbeddingModel(dim=128)

    chunks = [
        DocumentChunk(chunk_id="c1", doc_id="d1", content="Python docs", index=0,
                      metadata={"category": "programming", "lang": "python"}),
        DocumentChunk(chunk_id="c2", doc_id="d1", content="Java docs", index=1,
                      metadata={"category": "programming", "lang": "java"}),
    ]
    embeddings = await embedding.embed([c.content for c in chunks])
    await store.add(chunks, embeddings)

    query_vec = await embedding.embed_query("docs")
    results = await store.search(query_vec, top_k=5, filters={"lang": "python"})
    assert len(results) == 1
    assert "Python" in results[0].chunk.content


@pytest.mark.asyncio
async def test_memory_vector_store_cosine_similarity():
    # Test with known vectors
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert MemoryVectorStore._cosine_similarity(a, b) == 1.0

    c = [0.0, 1.0, 0.0]
    assert MemoryVectorStore._cosine_similarity(a, c) == 0.0


@pytest.mark.asyncio
async def test_memory_vector_store_empty_search():
    store = MemoryVectorStore()
    query_vec = [0.1] * 128
    results = await store.search(query_vec, top_k=5)
    assert len(results) == 0


# ======================== RAG Pipeline Tests ========================

@pytest.mark.asyncio
async def test_rag_pipeline_add_and_query():
    embedding = DummyEmbeddingModel(dim=128)
    store = MemoryVectorStore()

    pipeline = RAGPipeline(
        vector_store=store,
        embedding_model=embedding,
    )

    doc = Document(doc_id="d1", content="Python is a versatile programming language used for web development, data science, and automation.", doc_type=DocumentType.TEXT)
    await pipeline.add_document(doc, TextChunker(chunk_size=200))

    result = await pipeline.query("What is Python used for?")
    assert result.query == "What is Python used for?"
    assert len(result.sources) >= 1
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_rag_pipeline_search_only():
    embedding = DummyEmbeddingModel(dim=128)
    store = MemoryVectorStore()

    pipeline = RAGPipeline(
        vector_store=store,
        embedding_model=embedding,
    )

    doc = Document(doc_id="d1", content="Machine learning is a subset of artificial intelligence.", doc_type=DocumentType.TEXT)
    await pipeline.add_document(doc)

    results = await pipeline.search("What is machine learning?")
    assert len(results) >= 1
    assert "machine learning" in results[0].chunk.content.lower()


@pytest.mark.asyncio
async def test_rag_pipeline_stats():
    embedding = DummyEmbeddingModel(dim=128)
    store = MemoryVectorStore()
    pipeline = RAGPipeline(vector_store=store, embedding_model=embedding)

    doc = Document(doc_id="d1", content="Test content", doc_type=DocumentType.TEXT)
    await pipeline.add_document(doc)

    stats = await pipeline.get_stats()
    assert stats["total_chunks"] >= 1


@pytest.mark.asyncio
async def test_rag_pipeline_no_results():
    embedding = DummyEmbeddingModel(dim=128)
    store = MemoryVectorStore()
    pipeline = RAGPipeline(vector_store=store, embedding_model=embedding)

    result = await pipeline.query("nonexistent topic")
    assert result.query == "nonexistent topic"
    assert len(result.sources) == 0


# ======================== KnowledgeBase Manager Tests ========================

@pytest.mark.asyncio
async def test_knowledge_base_create_and_query():
    mgr = KnowledgeBaseManager()

    kb = await mgr.create_kb("kb_001", "Tech Knowledge Base", "Technology docs")
    assert kb.kb_id == "kb_001"
    assert kb.name == "Tech Knowledge Base"

    doc = Document(doc_id="d1", content="HiveFlow is a multi-agent platform with blackboard system.", doc_type=DocumentType.TEXT)
    await mgr.add_document("kb_001", doc)

    assert kb.doc_count == 1
    assert kb.chunk_count >= 1


@pytest.mark.asyncio
async def test_knowledge_base_remove_document():
    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_002", "Test KB")

    doc = Document(doc_id="d1", content="Content A", doc_type=DocumentType.TEXT)
    await mgr.add_document("kb_002", doc)

    kb = (await mgr.list_kbs())[0]
    initial_chunks = kb.chunk_count

    deleted = await mgr.remove_document("kb_002", "d1")
    assert deleted >= 1


@pytest.mark.asyncio
async def test_knowledge_base_delete():
    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_003", "Temp KB")

    assert await mgr.delete_kb("kb_003")
    kbs = await mgr.list_kbs()
    assert all(kb.kb_id != "kb_003" for kb in kbs)


@pytest.mark.asyncio
async def test_knowledge_base_search():
    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_search", "Search KB")

    doc = Document(doc_id="d1", content="The RAG pipeline retrieves relevant documents before generating answers.", doc_type=DocumentType.TEXT)
    await mgr.add_document("kb_search", doc)

    results = await mgr.search("kb_search", "What is RAG?")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_knowledge_base_not_found():
    mgr = KnowledgeBaseManager()
    with pytest.raises(ValueError, match="not found"):
        await mgr.add_document("nonexistent", Document(doc_id="d1", content="", doc_type=DocumentType.TEXT))

    with pytest.raises(ValueError, match="not found"):
        await mgr.query("nonexistent", "query")


# ======================== MCP Client Tests ========================

@pytest.mark.asyncio
async def test_mcp_mock_client_initialize():
    client = MCPClient(transport="mock")
    await client.initialize()
    assert client.is_connected()


@pytest.mark.asyncio
async def test_mcp_mock_register_tool():
    client = MCPClient(transport="mock")
    await client.initialize()

    def echo_handler(args):
        """
        - text: The text to echo back
        """
        return {"echo": args.get("text", "")}

    client.register_tool("echo", echo_handler)
    tools = await client.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "echo"


@pytest.mark.asyncio
async def test_mcp_mock_call_tool():
    client = MCPClient(transport="mock")
    await client.initialize()

    client.register_tool("add", lambda args: {"result": args.get("a", 0) + args.get("b", 0)})
    result = await client.call_tool("add", {"a": 3, "b": 5})

    assert result.success
    assert result.tool_name == "add"
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_mcp_mock_call_nonexistent_tool():
    client = MCPClient(transport="mock")
    await client.initialize()

    result = await client.call_tool("nonexistent", {})
    assert not result.success
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_mcp_register_multiple_tools():
    client = MCPClient(transport="mock")
    await client.initialize()

    client.register_tools({
        "greet": lambda args: {"greeting": f"Hello, {args.get('name', 'World')}"},
        "calculate": lambda args: {"result": args.get("x", 0) * 2},
    })

    tools = await client.list_tools()
    assert len(tools) == 2
    tool_names = {t.name for t in tools}
    assert "greet" in tool_names
    assert "calculate" in tool_names


@pytest.mark.asyncio
async def test_mcp_tool_result_latency():
    client = MCPClient(transport="mock")
    await client.initialize()

    client.register_tool("slow", lambda args: {"status": "ok"})
    result = await client.call_tool("slow", {})
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_mcp_tool_error_handling():
    client = MCPClient(transport="mock")
    await client.initialize()

    def failing_tool(args):
        raise ValueError("Something went wrong")

    client.register_tool("fail", failing_tool)
    result = await client.call_tool("fail", {})

    assert not result.success
    assert "Something went wrong" in result.error


# ======================== MCP Plugin Manager Tests ========================

@pytest.mark.asyncio
async def test_mcp_plugin_register():
    mgr = MCPPluginManager()

    plugin = await mgr.register_plugin(
        plugin_id="test_plugin",
        name="Test Plugin",
        description="A test plugin",
        transport="mock",
    )

    assert plugin.plugin_id == "test_plugin"
    assert plugin.name == "Test Plugin"
    assert plugin.transport == "mock"


@pytest.mark.asyncio
async def test_mcp_plugin_initialize():
    mgr = MCPPluginManager()

    await mgr.register_plugin(
        plugin_id="mock_plugin",
        name="Mock Plugin",
        transport="mock",
    )

    await mgr.initialize_plugin("mock_plugin")
    tools = await mgr.get_plugin_tools("mock_plugin")
    assert isinstance(tools, list)


@pytest.mark.asyncio
async def test_mcp_plugin_call_tool():
    mgr = MCPPluginManager()

    await mgr.register_plugin(
        plugin_id="calc_plugin",
        name="Calculator",
        transport="mock",
    )

    # Register tools on the underlying client
    await mgr.initialize_plugin("calc_plugin")

    # Access the client to register tools
    client = mgr._clients["calc_plugin"]
    client.register_tool("multiply", lambda args: {"result": args.get("a", 1) * args.get("b", 1)})

    result = await mgr.call_tool("calc_plugin", "multiply", {"a": 6, "b": 7})
    assert result.success
    assert "42" in result.content


@pytest.mark.asyncio
async def test_mcp_plugin_remove():
    mgr = MCPPluginManager()

    await mgr.register_plugin(
        plugin_id="temp_plugin",
        name="Temp",
        transport="mock",
    )

    assert await mgr.remove_plugin("temp_plugin")
    assert not await mgr.remove_plugin("nonexistent")


@pytest.mark.asyncio
async def test_mcp_plugin_list():
    mgr = MCPPluginManager()

    await mgr.register_plugin("p1", "Plugin 1", transport="mock")
    await mgr.register_plugin("p2", "Plugin 2", transport="mock")

    plugins = await mgr.list_plugins()
    assert len(plugins) == 2


@pytest.mark.asyncio
async def test_mcp_plugin_stats():
    mgr = MCPPluginManager()

    await mgr.register_plugin("stats_plugin", "Stats", transport="mock")
    await mgr.initialize_plugin("stats_plugin")

    # Add a tool to the client and update plugin.tools
    client = mgr._clients["stats_plugin"]
    client.register_tool("tool1", lambda args: {})

    # Refresh plugin tools
    plugin = await mgr.get_plugin("stats_plugin")
    plugin.tools = await client.list_tools()

    stats = mgr.get_stats()
    assert stats["total_plugins"] == 1
    assert stats["enabled_plugins"] == 1
    assert stats["total_tools"] == 1


@pytest.mark.asyncio
async def test_mcp_plugin_not_found():
    mgr = MCPPluginManager()
    with pytest.raises(ValueError, match="not found"):
        await mgr.initialize_plugin("nonexistent")

    with pytest.raises(ValueError, match="not found"):
        await mgr.get_plugin_tools("nonexistent")


@pytest.mark.asyncio
async def test_mcp_plugin_get():
    mgr = MCPPluginManager()
    await mgr.register_plugin("get_plugin", "Get Me", transport="mock")

    plugin = await mgr.get_plugin("get_plugin")
    assert plugin is not None
    assert plugin.name == "Get Me"

    plugin_none = await mgr.get_plugin("nonexistent")
    assert plugin_none is None


# ======================== Integration Tests ========================

@pytest.mark.asyncio
async def test_rag_with_multiple_documents():
    """Test RAG pipeline with multiple documents."""
    embedding = DummyEmbeddingModel(dim=128)
    store = MemoryVectorStore()
    pipeline = RAGPipeline(vector_store=store, embedding_model=embedding)

    docs = [
        Document(doc_id="d1", content="Python is a programming language created by Guido van Rossum.", doc_type=DocumentType.TEXT),
        Document(doc_id="d2", content="JavaScript is used for web development and runs in browsers.", doc_type=DocumentType.TEXT),
        Document(doc_id="d3", content="Rust is a systems programming language focused on safety.", doc_type=DocumentType.TEXT),
    ]

    for doc in docs:
        await pipeline.add_document(doc)

    stats = await pipeline.get_stats()
    assert stats["total_chunks"] >= 3

    results = await pipeline.search("web development")
    assert len(results) >= 1
    assert any("JavaScript" in r.chunk.content or "web" in r.chunk.content.lower() for r in results)


@pytest.mark.asyncio
async def test_knowledge_base_with_multiple_documents():
    """Test KnowledgeBaseManager with multiple documents."""
    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_multi", "Multi-doc KB")

    docs = [
        Document(doc_id="d1", content="Document one about AI.", doc_type=DocumentType.TEXT),
        Document(doc_id="d2", content="Document two about ML.", doc_type=DocumentType.TEXT),
        Document(doc_id="d3", content="Document three about NLP.", doc_type=DocumentType.TEXT),
    ]

    for doc in docs:
        await mgr.add_document("kb_multi", doc)

    kb = (await mgr.list_kbs())[0]
    assert kb.doc_count == 3
    assert kb.chunk_count >= 3


@pytest.mark.asyncio
async def test_mcp_integration_with_rag():
    """Test MCP tools can be used to query knowledge base."""
    # Setup RAG
    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_mcp", "MCP KB")
    doc = Document(doc_id="d1", content="HiveFlow supports MCP protocol for plugin integration.", doc_type=DocumentType.TEXT)
    await mgr.add_document("kb_mcp", doc)

    # Setup MCP
    mcp_mgr = MCPPluginManager()
    await mcp_mgr.register_plugin("rag_plugin", "RAG Plugin", transport="mock")
    await mcp_mgr.initialize_plugin("rag_plugin")

    client = mcp_mgr._clients["rag_plugin"]
    client.register_tool("query_kb", lambda args: mgr.search("kb_mcp", args.get("query", "")))

    result = await mcp_mgr.call_tool("rag_plugin", "query_kb", {"query": "HiveFlow"})
    assert result.success


@pytest.mark.asyncio
async def test_chunk_metadata_preservation():
    """Test that chunk metadata are preserved."""
    chunker = TextChunker(chunk_size=50)
    doc = Document(doc_id="d1", content="Short content", doc_type=DocumentType.TEXT, metadata={"author": "test", "version": "1.0"})
    chunks = chunker.chunk(doc)

    assert len(chunks) >= 1
    assert chunks[0].metadata["author"] == "test"
    assert chunks[0].metadata["version"] == "1.0"


@pytest.mark.asyncio
async def test_rag_result_sources():
    """Test that RAG result contains proper source information."""
    embedding = DummyEmbeddingModel(dim=128)
    store = MemoryVectorStore()
    pipeline = RAGPipeline(vector_store=store, embedding_model=embedding)

    doc = Document(doc_id="d1", content="Test content for source verification.", doc_type=DocumentType.TEXT, metadata={"source": "test.txt"})
    await pipeline.add_document(doc)

    result = await pipeline.query("Test content")
    if result.sources:
        assert result.sources[0].chunk.metadata.get("source") == "test.txt"
        # Score can be positive or negative depending on embedding distance
        assert isinstance(result.sources[0].score, float)
