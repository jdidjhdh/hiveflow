"""
HiveFlow - 06: RAG Pipeline

This example demonstrates Retrieval-Augmented Generation with document processing.

Usage:
    python 06_rag_pipeline.py
"""
import asyncio
from hiveflow import (
    DocumentProcessor,
    TextChunker,
    MemoryVectorStore,
    RAGPipeline,
    DummyEmbeddingModel,
    KnowledgeBaseManager,
)


async def main():
    print("=== RAG Pipeline Example ===\n")

    kb_manager = KnowledgeBaseManager()
    kb = await kb_manager.create_kb(
        kb_id="ai-docs",
        name="AI Documentation",
        description="Knowledge base for AI-related documents",
    )
    print(f"Created knowledge base: {kb.name}")

    processor = DocumentProcessor()
    chunker = TextChunker(chunk_size=500, chunk_overlap=50)

    documents = [
        ("Introduction to AI", "Artificial Intelligence enables machines to perform tasks that require human intelligence."),
        ("Machine Learning Basics", "Machine learning enables systems to learn patterns from data without explicit programming."),
        ("Deep Learning Overview", "Deep learning uses neural networks with many layers to model complex patterns."),
    ]

    print("\nIndexing documents...")
    for title, content in documents:
        doc = processor.parse_text(content, source=title)
        await kb_manager.add_document(kb.kb_id, doc, chunker)
        print(f"  Indexed: {title}")

    query = "What is artificial intelligence?"
    result = await kb_manager.query(kb.kb_id, query)

    print(f"\nQuery: {query}")
    print(f"Answer: {result.answer or '(retrieval-only - add llm_client for generation)'}")
    print(f"Sources retrieved: {len(result.sources)}")
    for i, source in enumerate(result.sources, 1):
        print(f"  {i}. score={source.score:.3f} - {source.chunk.content[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
