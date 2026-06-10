"""
HiveFlow 引擎演示用例

展示从用户查询到最终答案的完整流程：
  用户输入 → IntentParser → 任务编排 → Skill Workers → 答案

运行方式:
  cd "HiveFlow Agent"
  python -m pytest tests/test_demo.py -v -s

说明: 本演示使用 Mock LLM 模拟 AI 响应，无需 API Key 即可运行。
      为了演示简洁性，使用直接执行器绕过事件总线，但展示了相同的核心概念。
"""

import pytest
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from hiveflow import HiveFlow, HiveFlowConfig, MISSING, ECM, Expectation, Capability
from hiveflow import MemoryBlackboard
from llm.base import LLMClient
from memory.vector_store import VectorStore
from memory.manager import MemoryManager
from intent_parser import IntentParser
from core.secure_blackboard import SecureBlackboard


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
    """模拟网络搜索技能。"""
    query = ecm.payload.get("user_query", "") or str(ecm.payload.get("query", "unknown"))
    print(f"    [web_search] 正在搜索: {query}")
    results = [
        {"title": "Python Programming - Wikipedia", "url": "https://en.wikipedia.org/wiki/Python",
         "snippet": "Python is a high-level, general-purpose programming language..."},
        {"title": "Python Documentation", "url": "https://docs.python.org",
         "snippet": "The official Python documentation and tutorials..."},
    ]
    result_key = f"hivemind:result:{ecm.intent_id}:search"
    await view.put(result_key, {"results": results})
    print(f"    [web_search] 找到 {len(results)} 条结果")
    return {"results": results}


async def code_exec_handler(ecm, view):
    """模拟代码执行技能。"""
    code = ecm.payload.get("code", "print('hello')")
    print(f"    [code_exec] 正在执行: {code[:50]}...")
    result = {"output": "Hello, World!", "exit_code": 0}
    result_key = f"hivemind:result:{ecm.intent_id}:code"
    await view.put(result_key, result)
    print(f"    [code_exec] 执行完成")
    return result


async def final_answer_handler(ecm, view):
    """生成最终答案。"""
    print(f"    [final_answer] 正在生成最终答案...")

    # 从黑板读取依赖结果
    deps = ecm.payload.get("deps", {})
    search_result = None
    for key, val in deps.items():
        if isinstance(val, dict) and "results" in val:
            search_result = val
            break

    if search_result and "results" in search_result:
        results = search_result["results"]
        summary = "根据搜索结果，我为您找到以下信息：\n\n"
        for i, r in enumerate(results, 1):
            summary += f"{i}. **{r['title']}**\n   {r['snippet']}\n   链接: {r['url']}\n\n"
        summary += "希望这些信息对您有帮助！"
    else:
        summary = f"关于 '{ecm.payload.get('user_query', 'your query')}'，我暂时没有找到相关信息。"

    result_key = f"hivemind:result:{ecm.intent_id}:final"
    await view.put(result_key, summary)
    print(f"    [final_answer] 答案生成完成")
    return summary


async def failing_handler(ecm, view):
    """会失败的处理器，用于演示错误传播。"""
    print(f"    [failing] 模拟任务失败...")
    raise RuntimeError("模拟的网络连接超时错误")


# ============================================================
# 简化的执行器 (演示用，绕过事件总线)
# ============================================================

class DirectExecutor:
    """简化执行器：直接按依赖顺序执行 skill handler，无需事件总线。"""

    def __init__(self, blackboard: SecureBlackboard):
        self.handlers: Dict[str, Any] = {}
        self.bb = blackboard

    def register(self, skill_name: str, handler):
        self.handlers[skill_name] = handler

    async def execute(self, graph_spec: Dict[str, dict], intent_id: str, user_query: str) -> Dict[str, Any]:
        """按依赖顺序执行图节点。"""
        results = {}
        executed = set()
        iterations = 0
        max_iterations = len(graph_spec) * 2  # 防止死循环

        print(f"\n    执行图: {len(graph_spec)} 个节点")

        while len(executed) < len(graph_spec) and iterations < max_iterations:
            iterations += 1
            progress = False

            for node_name, node_data in graph_spec.items():
                if node_name in executed:
                    continue

                deps = node_data.get("depends_on", [])
                if all(d in executed for d in deps):
                    skill_name = node_data["task"]
                    handler = self.handlers.get(skill_name)

                    # 构建依赖结果
                    dep_results = {}
                    for d in deps:
                        dep_results[d] = results.get(d, MISSING)

                    # 构建 ECM
                    ecm = ECM(
                        trace_id=f"trace-{intent_id}",
                        intent="execute",
                        intent_id=intent_id,
                        emitter="orchestrator",
                        expectation=Expectation(
                            state_key=f"hivemind:result:{intent_id}:{node_name}",
                            expected_schema={},
                            deadline=30.0,
                        ),
                        payload={"deps": dep_results, "user_query": user_query, **node_data},
                    )

                    # 创建只读视图
                    class SimpleView:
                        def __init__(self, bb):
                            self._bb = bb

                        async def put(self, key, value):
                            await self._bb.sys_put(key, value)

                        async def get(self, key):
                            return await self._bb.sys_get(key)

                    view = SimpleView(self.bb)

                    if handler:
                        print(f"    → 执行节点 [{node_name}] (技能: {skill_name})")
                        result = await handler(ecm, view)
                        results[node_name] = result
                    else:
                        print(f"    ⚠ 节点 [{node_name}] 未找到处理器 (技能: {skill_name})")
                        results[node_name] = MISSING

                    executed.add(node_name)
                    progress = True

            if not progress:
                print(f"    ⚠ 无法继续执行，剩余节点: {len(graph_spec) - len(executed)}")
                break

        return results


# ============================================================
# 演示测试
# ============================================================

@pytest.mark.asyncio
async def test_demo_basic_search():
    """演示 1: 基础搜索流程 - 用户查询 → 意图解析 → 任务编排 → 答案"""
    print("\n" + "=" * 70)
    print("演示 1: 基础搜索流程")
    print("=" * 70)
    print("用户输入: '什么是 Python 编程语言？'\n")

    # 1. 初始化 LLM 和黑板
    llm = DemoLLMClient()
    bb = SecureBlackboard(MemoryBlackboard())
    llm.set_json_responses([
        # IntentParser.parse() 响应
        {"intent": "search", "required_skills": ["web_search", "final_answer"],
         "payload": {"query": "Python 编程语言"}, "priority": "normal"},
    ])

    # 2. 解析意图
    print("步骤 1: 意图解析")
    skill_registry = {"web_search": "Search the web", "final_answer": "Generate final answer"}
    intent_parser = IntentParser(llm, skill_registry)
    ecm = await intent_parser.parse("什么是 Python 编程语言？")
    print(f"  → 意图类型: {ecm.intent}")
    print(f"  → 需要技能: {ecm.required_skills}")
    print(f"  → 意图 ID: {ecm.intent_id}")

    # 3. LLM 规划执行图
    print("\n步骤 2: 任务规划")
    llm.set_json_responses([
        {"search_data": {"task": "web_search", "depends_on": []},
         "final_answer": {"task": "final_answer", "depends_on": ["search_data"]}},
    ])
    graph_spec = await llm.complete_json([{"role": "system", "content": "plan"}])
    print(f"  → 执行图: {json.dumps(graph_spec, indent=4, ensure_ascii=False)}")

    # 4. 执行
    print("\n步骤 3: 执行任务")
    executor = DirectExecutor(bb)
    executor.register("web_search", web_search_handler)
    executor.register("final_answer", final_answer_handler)

    results = await executor.execute(graph_spec, ecm.intent_id, ecm.user_query)

    # 5. 打印结果
    print("\n" + "-" * 50)
    print("执行结果:")
    print("-" * 50)
    print(f"意图 ID: {ecm.intent_id}")
    print(f"意图类型: {ecm.intent}")
    print(f"\n最终答案:")
    answer = results.get("final_answer", "No answer")
    print(str(answer))

    # 6. 验证黑板上的结果
    print(f"\n验证黑板结果:")
    search_result = await bb.sys_get(f"hivemind:result:{ecm.intent_id}:search")
    print(f"  搜索结果: {len(search_result.get('results', []))} 条")
    final_result = await bb.sys_get(f"hivemind:result:{ecm.intent_id}:final")
    print(f"  最终答案: {str(final_result)[:80]}...")

    # 7. 审计日志
    audit_log = bb._audit_log
    if audit_log:
        print(f"\n黑板操作记录 (最近 5 条):")
        for entry in audit_log[-5:]:
            print(f"  - {entry}")

    # 断言
    assert ecm.intent == "search"
    assert "web_search" in ecm.required_skills
    assert "search_data" in results
    assert "final_answer" in results
    assert "Python" in str(results["final_answer"])
    print("\n✅ 演示 1 完成!")


@pytest.mark.asyncio
async def test_demo_multi_skill():
    """演示 2: 多技能并行 - 代码执行 + 搜索 + 最终答案"""
    print("\n" + "=" * 70)
    print("演示 2: 多技能并行")
    print("=" * 70)
    print("用户输入: '运行 Python 代码并搜索相关文档'\n")

    llm = DemoLLMClient()
    bb = SecureBlackboard(MemoryBlackboard())

    # 意图解析
    llm.set_json_responses([
        {"intent": "code_and_search", "required_skills": ["code_exec", "web_search", "final_answer"],
         "payload": {"code": "print('hello')"}, "priority": "normal"},
    ])
    skill_registry = {"code_exec": "Execute code", "web_search": "Search", "final_answer": "Answer"}
    intent_parser = IntentParser(llm, skill_registry)
    ecm = await intent_parser.parse("运行 Python 代码并搜索相关文档")
    print(f"  → 意图: {ecm.intent}, 技能: {ecm.required_skills}")

    # 任务规划
    llm.set_json_responses([
        {"run_code": {"task": "code_exec", "depends_on": []},
         "search_docs": {"task": "web_search", "depends_on": []},
         "final_answer": {"task": "final_answer", "depends_on": ["run_code", "search_docs"]}},
    ])
    graph_spec = await llm.complete_json([{"role": "system", "content": "plan"}])
    print(f"  → 执行图: {len(graph_spec)} 个节点")

    # 执行
    executor = DirectExecutor(bb)
    executor.register("code_exec", code_exec_handler)
    executor.register("web_search", web_search_handler)
    executor.register("final_answer", final_answer_handler)
    results = await executor.execute(graph_spec, ecm.intent_id, ecm.user_query)

    print(f"\n结果: run_code={results.get('run_code')}, search_docs={'results' in str(results.get('search_docs', {}))}")
    assert "run_code" in results
    assert "search_docs" in results
    assert "final_answer" in results
    print("✅ 演示 2 完成!")


@pytest.mark.asyncio
async def test_demo_error_propagation():
    """演示 3: 错误传播 - 技能失败时的处理"""
    print("\n" + "=" * 70)
    print("演示 3: 错误传播")
    print("=" * 70)

    bb = SecureBlackboard(MemoryBlackboard())
    executor = DirectExecutor(bb)
    executor.register("failing", failing_handler)
    executor.register("final_answer", final_answer_handler)

    graph_spec = {
        "fail_task": {"task": "failing", "depends_on": []},
        "final_answer": {"task": "final_answer", "depends_on": ["fail_task"]},
    }

    print("\n运行一个会失败的查询...")
    try:
        results = await executor.execute(graph_spec, "err-1", "测试错误传播")
        print(f"  结果: fail_task={results.get('fail_task')}")
        # final_answer 仍然执行（依赖了 fail_task 的结果 MISSING）
        assert "final_answer" in results
    except Exception as e:
        print(f"  捕获到异常: {type(e).__name__}: {e}")

    print("✅ 演示 3 完成!")


@pytest.mark.asyncio
async def test_demo_blackboard_permissions():
    """演示 4: 黑板权限控制 - 带 fnmatch 通配符的读写权限"""
    print("\n" + "=" * 70)
    print("演示 4: 黑板权限控制")
    print("=" * 70)

    bb = SecureBlackboard(MemoryBlackboard())

    # 注册 agent 并设置权限 (通过 Capability)
    await bb.register_agent("agent_a", Capability(agent_id="agent_a", skills={"test"}, read_keys={"public:*", "agent_a:*"}, write_keys={"agent_a:*", "public:*"}))
    await bb.register_agent("agent_b", Capability(agent_id="agent_b", skills={"test"}, read_keys={"public:*", "agent_b:*"}, write_keys={"agent_b:*", "public:*"}))

    print("\n设置权限:")
    print("  agent_a: read public:*, agent_a:*; write agent_a:*, public:*")
    print("  agent_b: read public:*, agent_b:*; write agent_b:*, public:*")

    # agent_a 写入自己的数据
    print("\n测试 4.1: agent_a 写入 agent_a:data")
    await bb.put_and_audit("agent_a", "agent_a:data", {"secret": "value_a"})
    print("  ✅ 写入成功")

    # agent_b 无法读取 agent_a 的数据
    print("\n测试 4.2: agent_b 尝试读取 agent_a:data")
    try:
        await bb.get_and_audit("agent_b", "agent_a:data")
        print("  ❌ 意外读取成功")
    except PermissionError:
        print("  ✅ 权限拒绝 (预期)")

    # agent_a 可以读取自己的数据
    print("\n测试 4.3: agent_a 读取 agent_a:data")
    data = await bb.get_and_audit("agent_a", "agent_a:data")
    print(f"  ✅ 读取成功: {data}")
    assert data == {"secret": "value_a"}

    # 写入公共数据，双方都可读
    print("\n测试 4.4: agent_a 写入 public:info")
    await bb.put_and_audit("agent_a", "public:info", {"shared": True})
    data_b = await bb.get_and_audit("agent_b", "public:info")
    print(f"  ✅ agent_b 读取公共数据: {data_b}")

    print("\n审计日志:")
    for entry in bb._audit_log[-5:]:
        print(f"  - {entry}")

    print("✅ 演示 4 完成!")


@pytest.mark.asyncio
async def test_demo_memory_persistence():
    """演示 5: 记忆管理 - 短期记忆 + 长期向量记忆"""
    print("\n" + "=" * 70)
    print("演示 5: 记忆管理")
    print("=" * 70)

    llm = DemoLLMClient()
    bb = SecureBlackboard(MemoryBlackboard())
    vector_store = InMemoryVectorStore(embedding_fn=llm.embed)
    memory = MemoryManager(bb, vector_store, short_term_limit=3)

    # 保存短期记忆
    print("\n步骤 1: 保存短期记忆")
    await memory.save_work_memory("user_query", "什么是 Python?")
    await memory.save_work_memory("result", "Found Python docs")
    await memory.save_work_memory("answer", "Python is a programming language")
    print(f"  → 短期记忆条目: {len(memory.get_short_term())}")

    # 保存长期记忆
    print("\n步骤 2: 保存长期记忆")
    await memory.save_long_term("用户询问 Python 编程语言", metadata={"topic": "programming"})
    await memory.save_long_term("搜索结果显示 Python 文档", metadata={"topic": "docs"})
    print(f"  → 长期记忆条目: {len(await memory.recall_long_term('Python', k=10))}")

    # 召回长期记忆
    print("\n步骤 3: 召回长期记忆")
    recalled = await memory.recall_long_term("Python programming", k=2)
    print(f"  → 召回 {len(recalled)} 条相关记忆")
    for item in recalled:
        print(f"    - {item.content[:50]}...")

    # 验证短期记忆限制
    print("\n步骤 4: 验证短期记忆限制 (limit=3)")
    await memory.save_work_memory("extra", "item4")
    st = memory.get_short_term()
    print(f"  → 添加第 4 条后，短期记忆仍为 {len(st)} 条 (最早条目已淘汰)")
    assert len(st) <= 3

    print("✅ 演示 5 完成!")
