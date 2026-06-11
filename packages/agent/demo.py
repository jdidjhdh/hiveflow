"""
HiveMind Agent 演示 — 使用 HiveMindApp + 正确结果键协议。

运行:
  cd packages/agent && python demo.py
"""

import asyncio
import logging
from typing import List

from hiveflow import HiveFlowConfig

from app import HiveMindApp, HiveMindConfig
from llm.base import LLMClient
from memory.vector_store import VectorStore

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class DemoLLMClient(LLMClient):
    def __init__(self):
        self._json_responses: List[dict] = []
        self._json_idx = 0

    def set_json_responses(self, responses):
        self._json_responses = list(responses)
        self._json_idx = 0

    async def complete(self, messages, **kwargs):
        return "done"

    async def complete_json(self, messages, **kwargs):
        if self._json_idx < len(self._json_responses):
            resp = self._json_responses[self._json_idx]
            self._json_idx += 1
            return resp
        return {}

    async def stream(self, messages, **kwargs):
        yield "done"

    async def embed(self, texts):
        return [[0.1] * 1536 for _ in texts]


class InMemoryVectorStore(VectorStore):
    def __init__(self, embedding_fn):
        self.embedding_fn = embedding_fn

    async def add_texts(self, texts, metadatas=None, ids=None):
        return ids or [f"doc_{i}" for i in range(len(texts))]

    async def similarity_search(self, query, k=5, filter_fn=None):
        return []

    async def delete(self, ids):
        pass


async def web_search_handler(ecm, view):
    query = ecm.payload.get("query", "unknown")
    print(f"    [web_search] 搜索: {query}")
    payload = {
        "results": [
            {"title": "Python - Wikipedia", "snippet": "Python is a high-level programming language."},
            {"title": "Python Docs", "snippet": "Official Python documentation."},
        ]
    }
    await view.put(f"hivemind:result:{ecm.intent_id}", payload)
    return payload


async def summarize_handler(ecm, view):
    print("    [summarize] 生成最终答案...")
    deps = ecm.payload.get("input_keys", {})
    search_data = {}
    for _name, key in deps.items():
        try:
            search_data = await view.get(key)
        except (KeyError, PermissionError):
            pass
    if search_data.get("results"):
        lines = [f"- {r['title']}: {r['snippet']}" for r in search_data["results"]]
        answer = "根据搜索结果:\n" + "\n".join(lines)
    else:
        answer = f"关于 '{ecm.payload.get('query', '')}' 暂无结果。"
    await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
    return {"answer": answer}


async def main():
    print("=" * 60)
    print("HiveMindApp 演示 — 意图解析 → 计划 → Skill 执行")
    print("=" * 60)

    llm = DemoLLMClient()
    llm.set_json_responses([
        {
            "intent": "search",
            "required_skills": ["web_search", "summarize"],
            "payload": {"query": "Python 编程语言"},
            "priority": "normal",
        },
        {
            "search_data": {"task": "web_search", "depends_on": []},
            "final_answer": {
                "task": "summarize",
                "depends_on": ["search_data"],
                "expectation": {"required_keys": ["answer"], "on_violation": "warn"},
            },
        },
    ])

    skills = {
        "web_search": "Search the web for information",
        "summarize": "Summarize upstream results into final answer",
    }

    config = HiveMindConfig(
        hiveflow_config=HiveFlowConfig(blackboard_type="memory", max_audit_entries=200),
        llm=llm,
        embedding_llm=llm,
        vector_store=InMemoryVectorStore(embedding_fn=llm.embed),
        skill_registry=skills,
        enable_result_cleanup=False,
    )
    app = HiveMindApp(config)
    await app.start()

    await app.create_skill_agent(
        "web_search", "web-agent", web_search_handler,
        read_keys=set(), write_keys={"hivemind:result:*"},
    )
    await app.create_skill_agent(
        "summarize", "sum-agent", summarize_handler,
        read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"},
    )

    result = await app.run_query("什么是 Python 编程语言？", conversation_id="demo-1")
    print("\n--- 结果 ---")
    print(f"intent_id: {result['intent_id']}")
    print(f"status: {result.get('status', 'completed')}")
    print(f"answer: {result['answer']}")

    audit = app.blackboard._audit_log[-5:]
    if audit:
        print("\n最近审计 (5 条):")
        for entry in audit:
            print(f"  {entry}")

    await app.shutdown()
    print("\n演示完成。")


if __name__ == "__main__":
    asyncio.run(main())
