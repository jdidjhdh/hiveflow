"""
HiveFlow Agent 性能/压力测试

测试场景:
1. 并发查询压力: 10 个并发查询，验证全部完成
2. 长期运行稳定性: 50 次顺序查询，验证无内存泄漏或性能退化
3. 内存管理器负载测试: 大量短期内存添加 + LRU 淘汰
4. 调度器吞吐量: 每秒可调度任务数量
"""

import pytest
import asyncio
import time
import sys
import os
from typing import List

# Ensure parent dir is on path so app module can be imported
_agent_tests_dir = os.path.dirname(os.path.abspath(__file__))
_agent_dir = os.path.dirname(_agent_tests_dir)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

_core_dir = os.path.normpath(os.path.join(_agent_dir, '..', 'HiveFlow Core'))
_core_dir = os.path.abspath(_core_dir)
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

from app import HiveMindApp, HiveMindConfig
from hiveflow import HiveFlowConfig
from llm.base import LLMClient
from memory.vector_store import VectorStore
from memory.manager import MemoryManager
from core.secure_blackboard import SecureBlackboard, MemoryBlackboard


# ============================================================
# Mock 组件 (复用自 test_integration_end_to_end.py)
# ============================================================

class MockLLMClient(LLMClient):
    """可预设 JSON 和文本响应的 Mock LLM。"""

    def __init__(self):
        self._json_responses = []
        self._text_responses = []
        self._json_idx = 0
        self._text_idx = 0

    def set_json_responses(self, responses):
        self._json_responses = list(responses)
        self._json_idx = 0

    def set_text_responses(self, responses):
        self._text_responses = list(responses)
        self._text_idx = 0

    async def complete(self, messages, **kwargs):
        if self._text_idx < len(self._text_responses):
            resp = self._text_responses[self._text_idx]
            self._text_idx += 1
            return resp
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


class MockVectorStore(VectorStore):
    def __init__(self, embedding_fn):
        self.embedding_fn = embedding_fn
        self._texts: List[str] = []
        self._metadatas: List[dict] = []

    async def add_texts(self, texts, metadatas=None, ids=None):
        self._texts.extend(texts)
        if metadatas:
            self._metadatas.extend(metadatas)
        else:
            self._metadatas.extend([{} for _ in texts])
        return ids or [f"doc_{i}" for i in range(len(texts))]

    async def similarity_search(self, query, k=5, filter_fn=None):
        results = []
        for i, text in enumerate(self._texts[:k]):
            results.append(type('obj', (object,), {
                'content': text,
                'metadata': self._metadatas[i] if i < len(self._metadatas) else {}
            })())
        return results

    async def delete(self, ids):
        pass


def _create_test_app(skill_signatures: dict, llm: MockLLMClient):
    """创建用于测试的 App，预注册 skills。"""
    embedding_llm = MockLLMClient()
    vs = MockVectorStore(embedding_fn=embedding_llm.embed)
    config = HiveFlowConfig(blackboard_type="memory")
    hive_config = HiveMindConfig(
        hiveflow_config=config,
        llm=llm,
        embedding_llm=embedding_llm,
        vector_store=vs,
        skill_registry=skill_signatures,
        enable_result_cleanup=False,
    )
    return HiveMindApp(hive_config)


# ============================================================
# 1. 并发查询压力测试
# ============================================================

@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_concurrent_queries_stress():
    """运行 10 个并发查询，验证全部成功完成。

    每个查询使用独立的 MockLLMClient 实例以避免响应竞争。
    """
    num_queries = 10
    skill_signatures = {
        "calc": "Calculate a value",
        "summarize": "Generate a final answer summary",
    }

    async def run_single_query(query_idx: int):
        llm = MockLLMClient()
        llm.set_json_responses([
            {
                "intent": f"calc_{query_idx}",
                "required_skills": ["calc"],
                "payload": {"value": query_idx},
                "priority": "normal",
            },
            {
                "calc_node": {"task": "calc", "depends_on": []},
                "final_answer": {"task": "summarize", "depends_on": ["calc_node"]},
            },
        ])
        llm.set_text_responses([f"Summary for query {query_idx}"])

        app = _create_test_app(skill_signatures, llm)
        await app.start()

        async def calc_handler(ecm, view):
            value = ecm.payload.get("value", 0)
            result = {"calculated": value * 3}
            await view.put(f"hivemind:result:{ecm.intent_id}", result)
            return result

        async def summarize_handler(ecm, view):
            answer = f"Query {query_idx} result"
            await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
            return {"answer": answer}

        await app.create_skill_agent("calc", "calc-agent", calc_handler,
                                     read_keys=set(), write_keys={"hivemind:result:*"})
        await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                     read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

        try:
            result = await app.run_query(f"并发查询 {query_idx}")
            return result
        finally:
            await app.shutdown()

    # 并发执行所有查询
    start = time.monotonic()
    results = await asyncio.gather(
        *[run_single_query(i) for i in range(num_queries)],
        return_exceptions=True,
    )
    elapsed = time.monotonic() - start

    # 验证全部成功（无异常）
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(failures) == 0, f"{len(failures)} queries failed: {failures}"

    # 验证每个查询都返回了 answer
    for i, r in enumerate(results):
        assert "answer" in r, f"Query {i} missing 'answer' in result"

    if elapsed == 0:
        elapsed = 0.001
    print(f"\n[PERF] {num_queries} concurrent queries completed in {elapsed:.2f}s "
          f"({num_queries / elapsed:.1f} queries/sec)")


# ============================================================
# 2. 长期运行稳定性测试
# ============================================================

@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_long_running_stability():
    """运行 50 次顺序查询，验证无内存泄漏或性能退化。

    检查:
    - 所有查询都成功完成
    - 最后 10 次查询的平均耗时不超过前 10 次的 3 倍
    """
    num_queries = 50
    skill_signatures = {
        "echo": "Echo the input",
        "summarize": "Generate a final answer summary",
    }

    llm = MockLLMClient()

    # 预生成所有需要的响应
    json_responses = []
    text_responses = []
    for i in range(num_queries):
        json_responses.extend([
            {
                "intent": f"echo_{i}",
                "required_skills": ["echo"],
                "payload": {"message": f"hello_{i}"},
                "priority": "normal",
            },
            {
                "echo_node": {"task": "echo", "depends_on": []},
                "final_answer": {"task": "summarize", "depends_on": ["echo_node"]},
            },
        ])
        text_responses.append(f"Summary {i}")

    llm.set_json_responses(json_responses)
    llm.set_text_responses(text_responses)

    app = _create_test_app(skill_signatures, llm)
    await app.start()

    async def echo_handler(ecm, view):
        msg = ecm.payload.get("message", "")
        result = {"echo": msg}
        await view.put(f"hivemind:result:{ecm.intent_id}", result)
        return result

    async def summarize_handler(ecm, view):
        answer = "Echo completed"
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}

    await app.create_skill_agent("echo", "echo-agent", echo_handler,
                                 read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                 read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    latencies = []
    for i in range(num_queries):
        start = time.monotonic()
        result = await app.run_query(f"顺序查询 {i}")
        elapsed = time.monotonic() - start
        latencies.append(elapsed)

        assert "answer" in result, f"Query {i} failed: missing 'answer'"

    await app.shutdown()

    # 性能退化检查
    first_10_avg = sum(latencies[:10]) / 10
    last_10_avg = sum(latencies[-10:]) / 10

    total_time = sum(latencies)
    print(f"\n[PERF] {num_queries} sequential queries completed in {total_time:.2f}s")
    print(f"  First 10 avg: {first_10_avg * 1000:.1f}ms")
    print(f"  Last 10 avg:  {last_10_avg * 1000:.1f}ms")

    # 最后 10 次不应比前 10 次慢 3 倍以上
    degradation_ratio = last_10_avg / first_10_avg if first_10_avg > 0 else 0
    assert degradation_ratio < 3.0, (
        f"Performance degradation detected: last 10 queries are {degradation_ratio:.1f}x "
        f"slower than first 10 ({last_10_avg * 1000:.1f}ms vs {first_10_avg * 1000:.1f}ms)"
    )


# ============================================================
# 3. 内存管理器负载测试
# ============================================================

@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_memory_manager_under_load():
    """测试内存管理器在大量短期内存添加和 LRU 淘汰下的表现。

    检查:
    - 快速添加大量短期记忆（100 条）
    - 验证 LRU 淘汰正确限制内存大小
    - 验证工作内存读写在高负载下正确
    - 验证长期记忆写入性能
    """
    bb = SecureBlackboard(MemoryBlackboard())
    short_term_limit = 10
    mem_manager = MemoryManager(bb, None, short_term_limit=short_term_limit)

    # --- 短期内存压力测试 ---
    num_adds = 100
    start = time.monotonic()
    for i in range(num_adds):
        mem_manager.add_to_short_term("user" if i % 2 == 0 else "assistant", f"message_{i}")
    st_elapsed = time.monotonic() - start

    # 验证 LRU 淘汰：不应超过 short_term_limit * 2
    st = mem_manager.get_short_term()
    max_allowed = short_term_limit * 2
    assert len(st) <= max_allowed, (
        f"Short-term memory exceeded limit: {len(st)} > {max_allowed}"
    )

    # 验证保留的是最近的消息
    assert st[-1]["content"] == f"message_{num_adds - 1}", "Last message should be the most recent"

    if st_elapsed == 0:
        st_elapsed = 0.001
    print(f"\n[PERF] {num_adds} short-term additions in {st_elapsed * 1000:.1f}ms "
          f"({num_adds / st_elapsed:.0f} ops/sec), retained {len(st)} messages")

    # --- 工作内存并发压力测试 ---
    num_work_items = 50
    start = time.monotonic()

    async def write_work(idx):
        await mem_manager.save_work_memory(f"work:key_{idx}", {"data": f"value_{idx}"})

    tasks = [write_work(i) for i in range(num_work_items)]
    await asyncio.gather(*tasks)
    wm_elapsed = time.monotonic() - start

    # 验证所有写入可读回
    for i in range(num_work_items):
        val = await mem_manager.load_work_memory(f"work:key_{i}")
        assert val == {"data": f"value_{i}"}, f"Work memory mismatch for key_{i}"

    print(f"[PERF] {num_work_items} concurrent work memory writes in {wm_elapsed * 1000:.1f}ms")

    # --- 长期记忆写入压力测试 (无真实 vector store) ---
    # MemoryManager 的 save_long_term 需要 vector_store，此处仅测接口调用
    # 使用 MockVectorStore
    vs = MockVectorStore(embedding_fn=lambda t: [[0.1] * 1536])
    mem_manager_with_vs = MemoryManager(bb, vs, short_term_limit=short_term_limit)

    num_long_term = 20
    start = time.monotonic()
    for i in range(num_long_term):
        await mem_manager_with_vs.save_long_term(
            f"Long-term content {i}",
            metadata={"index": i, "category": "stress_test"}
        )
    lt_elapsed = time.monotonic() - start
    if lt_elapsed == 0:
        lt_elapsed = 0.001
    print(f"[PERF] {num_long_term} long-term memory saves in {lt_elapsed * 1000:.1f}ms "
          f"({num_long_term / lt_elapsed:.0f} ops/sec)")


# ============================================================
# 4. 调度器吞吐量测试
# ============================================================

@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_scheduler_throughput():
    """测试每秒可以调度多少任务。

    检查:
    - 注册多个 worker
    - 快速调度大量 ECM 任务
    - 测量调度吞吐量 (tasks/sec)
    """
    from hiveflow import (
        InProcessScheduler, InProcessEventBus, SchedulerConfig,
        ECM, Capability
    )

    bus = InProcessEventBus()
    config = SchedulerConfig()
    sched = InProcessScheduler(bus=bus, config=config)
    await sched.start()

    # 注册多个 worker
    num_workers = 5
    for i in range(num_workers):
        cap = Capability(
            agent_id=f"agent-{i}",
            skills={f"skill-{i}", "shared_skill"},
            read_keys=set(),
            write_keys=set(),
        )
        cap.max_queue_size = 1000
        cap.state = "running"
        mock_worker = type('MockWorker', (), {'agent_id': f'agent-{i}'})()
        await sched.register_worker(mock_worker, cap)

    # 调度大量任务
    num_tasks = 200
    start = time.monotonic()
    for i in range(num_tasks):
        ecm = ECM(
            trace_id=f'task-{i}',
            intent='test',
            intent_id=f'intent-{i}',
            emitter='test',
            required_skills=['shared_skill'],
            priority='normal',
            payload={"index": i},
            timestamp=time.monotonic(),
        )
        await sched.schedule(ecm)
    elapsed = time.monotonic() - start

    if elapsed == 0:
        elapsed = 0.001

    throughput = num_tasks / elapsed
    print(f"\n[PERF] Scheduled {num_tasks} tasks in {elapsed:.3f}s "
          f"({throughput:.0f} tasks/sec)")

    # 吞吐量应 > 50 tasks/sec (保守阈值)
    assert throughput > 50, f"Scheduling throughput too low: {throughput:.0f} tasks/sec"

    await sched.close()
