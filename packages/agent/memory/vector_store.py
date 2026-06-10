import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional
from chromadb import PersistentClient


class MemoryItem:
    def __init__(self, id: str, content: str, metadata: dict = None, timestamp: float = 0.0):
        self.id = id
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = timestamp


class VectorStore(ABC):
    @abstractmethod
    async def add_texts(self, texts: List[str], metadatas: List[dict] = None, ids: List[str] = None): ...

    @abstractmethod
    async def similarity_search(self, query: str, k: int = 5) -> List[MemoryItem]: ...

    @abstractmethod
    async def delete(self, ids: List[str]): ...


class ChromaVectorStore(VectorStore):
    def __init__(self, path="./chroma_db", embedding_fn=None):
        self.client = PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection("hivemind_memory")
        self.embed = embedding_fn

    async def add_texts(self, texts, metadatas=None, ids=None):
        ids = ids or [str(uuid.uuid4()) for _ in texts]
        embeddings = None
        if self.embed:
            embeddings = await self.embed(texts)
        await asyncio.to_thread(
            self.collection.add,
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings
        )

    async def similarity_search(self, query: str, k: int = 5) -> List[MemoryItem]:
        q_embed = None
        if self.embed:
            q_embed = (await self.embed([query]))[0]
        if q_embed:
            results = await asyncio.to_thread(
                self.collection.query,
                query_embeddings=[q_embed],
                n_results=k
            )
        else:
            results = await asyncio.to_thread(
                self.collection.query,
                query_texts=[query],
                n_results=k
            )
        if not results['ids'] or not results['ids'][0]:
            return []
        items = []
        for i in range(len(results['ids'][0])):
            items.append(MemoryItem(
                id=results['ids'][0][i],
                content=results['documents'][0][i],
                metadata=results['metadatas'][0][i] if results['metadatas'] else {}
            ))
        return items

    async def delete(self, ids):
        await asyncio.to_thread(self.collection.delete, ids=ids)
