"""
HiveFlow 引擎演示用例 (独立运行版)

展示从用户查询到最终答案的完整流程：
  用户输入 → IntentParser → CognitiveOrchestrator → Skill Workers → 答案

运行方式:
  cd "HiveFlow Agent"
  python demo.py

说明: 本演示使用 Mock LLM 模拟 AI 响应，无需 API Key 即可运行。
"""

import asyncio
import sys
import os
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# ============================================================
# Path 设置 (与 conftest.py 一致)
# ============================================================
_agent_dir = os.path.dirname(os.path.abspath(__file__))
_core_dir = os.path.normpath(os.path.join(_agent_dir, '..', 'HiveFlow Core'))
_core_dir = os.path.abspath(_core_dir)
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

# 注册 hiveflow 包
import importlib.util
core_init_path = os.path.join(_core_dir, "__init__.py")
if os.path.exists(core_init_path) and "hiveflow" not in sys.modules:
    spec = importlib.util.spec_from_file_location("hiveflow", core_init_path)
    pkg = importlib.util.module_from_spec(spec)
    pkg.__path__ = [_core_dir]
    sys.modules["hiveflow"] = pkg
    spec.loader.exec_module(pkg)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 现在导入
from hiveflow import HiveFlow, HiveFlowConfig, MISSING
from llm.base import LLMClient
from memory.vector_store import VectorStore
from memory.manager import MemoryManager
from intent_parser import IntentParser
from orchestrator.cognitive import CognitiveOrchestrator


# ============================================================
# Mock 组件
# ============================================================

class DemoLLMClient(LLMClient):
    """模拟 LLM 客户端。"""
    def __init__(self):
        self._json_responses = []
        self._json_idx = 0

    def set_json_responses(self, responses):
        self._json_responses = responses
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
    """轻量级内存向量存储。"""
    def __init__(self, embedding_fn):
        self.embedding_fn = embedding_fn

    async def add_texts(self, texts, metadatas=None, ids=None):
        return ids or [f"doc_{i}" for i in range(len(texts))]

    async def similarity_search(self, query, k=5, filter_fn=None):
        return []

    async def delete(self, ids):
        pass


# ============================================================
# Skill Handlers
# ============================================================

async def web_search_handler(ecm, view):
    query = getattr(ecm, 'user_query', '') or str(ecm.payload.get("query", "unknown"))
    print(f"    [web_search] 正在搜索: {query}")
    results = [
        {"title": "Python Programming - Wikipedia", "url": "https://en.wikipedia.org/wiki/Python",
         "snippet": "Python is a high-level, general-purpose programming language..."},
        {"title": "Python Documentation", "url": "https://docs.python.org",
         "snippet": "The official Python documentation and tutorials..."},
    ]
    result_key = f"result:{ecm.intent_id}:search"
    await view.put(result_key, {"results": results})
    print(f"    [web_search] 找到 {len(results)} 条结果")
    return {"results": results}


async def final_answer_handler(ecm, view):
    print(f"    [final_answer] 正在生成最终答案...")
    deps = ecm.payload.get("deps", {})
    search_data = deps.get("search_data", {})

    if search_data and "results" in search_data:
        results = search_data["results"]
        summary = "根据搜索结果，我为您找到以下信息：\n\n"
        for i, r in enumerate(results, 1):
            summary += f"{i}. **{r['title']}**\n   {r['snippet']}\n   链接: {r['url']}\n\n"
        summary += "希望这些信息对您有帮助！"
    else:
        summary = f"关于 '{getattr(ecm, 'user_query', 'your query')}'，我暂时没有找到相关信息。"

    result_key = f"result:{ecm.intent_id}:final"
    await view.put(result_key, summary)
    print(f"    [final_answer] 答案生成完成")
    return summary


# ============================================================
# 工具函数
# ============================================================

@dataclass
class SkillBinding:
    skill_name: str
    agent_id: str
    handler: Any
    read_keys: set
    write_keys: set


async def make_handler(fn):
    async def handler(ecm, view):
        return await fn(ecm, view)
    return handler


# ============================================================
# 演示 1: 基础搜索流程
# ============================================================

async def demo_basic_search():
    print("\n" + "=" * 70)
    print("演示 1: 基础搜索流程")
    print("=" * 70)
    print("用户输入: '什么是 Python 编程语言？'\n")

    llm = DemoLLMClient()
    llm.set_json_responses([
        # IntentParser.parse() 响应
        {"intent": "search", "required_skills": ["web_search", "final_answer"],
         "payload": {"query": "Python 编程语言"}, "priority": "normal"},
        # CognitiveOrchestrator._plan() 响应
        {"search_data": {"task": "web_search", "depends_on": []},
         "final_answer": {"task": "final_answer", "depends_on": ["search_data"]}},
    ])

    core = HiveFlow(HiveFlowConfig(blackboard_type="memory", max_audit_entries=100))
    await core.start()

    vector_store = InMemoryVectorStore(embedding_fn=llm.embed)
    memory = MemoryManager(core.blackboard, vector_store, short_term_limit=5)
    skill_registry = {"web_search": "Search the web", "final_answer": "Generate final answer"}
    intent_parser = IntentParser(llm, skill_registry)

    await core.create_agent(
        agent_id="web_search_agent", skills={"web_search"},
        read_keys=set(), write_keys={"web:*"},
        task_handler=await make_handler(web_search_handler),
    )
    await core.create_agent(
        agent_id="final_answer_agent", skills={"final_answer"},
        read_keys={"result:*"}, write_keys={"final_answer:*"},
        task_handler=await make_handler(final_answer_handler),
    )

    skill_bindings = {
        "web_search": SkillBinding("web_search", "web_search_agent",
                                   await make_handler(web_search_handler), set(), {"web:*"}),
        "final_answer": SkillBinding("final_answer", "final_answer_agent",
                                     await make_handler(final_answer_handler), {"result:*"}, {"final_answer:*"}),
    }

    orchestrator = CognitiveOrchestrator(
        llm=llm, hiveflow=core,
        skill_bindings=skill_bindings, skill_signatures=skill_registry,
        memory_manager=memory, intent_parser=intent_parser,
        max_replan_attempts=2, global_timeout=60.0, node_result_ttl=300.0,
    )

    print("开始执行查询...")
    result = await orchestrator.execute("什么是 Python 编程语言？", conversation_id="demo-1")

    print("\n" + "-" * 50)
    print("执行结果:")
    print("-" * 50)
    print(f"意图 ID: {result['intent_id']}")
    print(f"意图类型: {result.get('intent', 'N/A')}")
    print(f"\n最终答案:")
    answer = result.get("results", {}).get("final_answer", "No answer")
    print(str(answer)[:500])

    audit_log = core.blackboard._audit_log
    if audit_log:
        print(f"\n黑板操作记录 (最近 5 条):")
        for entry in audit_log[-5:]:
            print(f"  - {entry}")

    await core.shutdown()
    print("\n演示 1 完成!")


# ============================================================
# 主入口
# ============================================================

async def main():
    print("╔" + "═" * 68 + "╗")
    print("║" + "HiveFlow 引擎演示".center(68) + "║")
    print("║" + "多智能体编排引擎 - 从查询到答案的完整流程".center(68) + "║")
    print("╚" + "═" * 68 + "╝")

    await demo_basic_search()

    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)
    print("\nHiveFlow 引擎核心能力:")
    print("  ✅ 意图解析 (IntentParser) - 将用户查询解析为结构化意图")
    print("  ✅ 认知编排 (CognitiveOrchestrator) - 自动规划任务依赖图")
    print("  ✅ 技能编排 (Skill Workers) - 并行/串行执行多个技能")
    print("  ✅ 安全黑板 (SecureBlackboard) - 带权限控制和审计日志")
    print("  ✅ 输入防护 (InputGuard) - 拦截危险输入")
    print("  ✅ 错误传播 - 技能失败时正确传递错误信息")
    print("  ✅ 内存管理 (MemoryManager) - 短期记忆 + 长期向量记忆")
    print("\n与 LangChain 对比:")
    print("  • LangChain: 链式 LLM 调用，适合单线任务")
    print("  • HiveFlow: 多智能体 DAG 编排，适合复杂并行任务")
    print("  • HiveFlow 优势: 技能隔离、权限控制、自动重试/重规划")


if __name__ == "__main__":
    asyncio.run(main())
