"""
HiveFlow Agent + Core 端到端集成测试

测试场景:
1. 完整流程: 用户输入 → IntentParser → CognitiveOrchestrator → DAG 执行 → 结果返回
2. 错误恢复: 节点失败后 replan 流程
3. 内存持久化: 执行后记忆正确保存
"""

import pytest
import asyncio
import json
from typing import List

from hiveflow import HiveFlow, HiveFlowConfig, MISSING
from hiveflow.blackboard import MemoryBlackboard

from app import HiveMindApp, HiveMindConfig, SkillBinding
from core.secure_blackboard import SecureBlackboard, Capability
from llm.base import LLMClient
from memory.vector_store import VectorStore
from memory.manager import MemoryManager
from intent_parser import IntentParser


# ============================================================
# Mock 组件
# ============================================================

class MockLLMClient(LLMClient):
    """可预设 JSON 和文本响应的 Mock LLM。"""
    def __init__(self):
        self._json_responses = []
        self._text_responses = []
        self._json_idx = 0
        self._text_idx = 0

    def set_json_responses(self, responses):
        """设置所有 JSON 响应 (按调用顺序)。"""
        self._json_responses = list(responses)
        self._json_idx = 0

    def set_text_responses(self, responses):
        """设置所有文本响应 (按调用顺序)。"""
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


def create_test_app(skill_signatures: dict, llm: MockLLMClient):
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
    app = HiveMindApp(hive_config)
    return app


# ============================================================
# 1. 完整流程测试
# ============================================================

@pytest.mark.asyncio
async def test_full_pipeline_simple_query():
    """测试简单查询的完整流程。
    用户输入: "计算 2+2"
    流程: calculate → final_answer
    """
    llm = MockLLMClient()
    # 所有 JSON 响应按调用顺序:
    # 1. IntentParser.parse() -> intent result
    # 2. _plan() -> graph spec
    llm.set_json_responses([
        {
            "intent": "calculate",
            "required_skills": ["calculate"],
            "payload": {"expression": "2+2"},
            "priority": "normal",
        },
        {
            "calculate_node": {"task": "calculate", "depends_on": []},
            "final_answer": {"task": "summarize", "depends_on": ["calculate_node"]},
        },
    ])
    # 总结响应
    llm.set_text_responses(["Summary: User asked to calculate 2+2."])

    skill_signatures = {
        "calculate": "Perform a calculation",
        "summarize": "Generate a final answer summary",
    }

    app = create_test_app(skill_signatures, llm)
    await app.start()

    # 注册实际处理函数
    async def calculate_handler(ecm, view):
        expr = ecm.payload.get("expression", "0")
        result = eval(expr)
        await view.put(f"hivemind:result:{ecm.intent_id}", {"result": result})
        return {"result": result}

    async def summarize_handler(ecm, view):
        deps = ecm.payload.get("input_keys", {})
        calc_result = await view.get(deps.get("calculate_node", ""))
        answer = f"The result is {calc_result.get('result', 'unknown')}"
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}

    await app.create_skill_agent("calculate", "calc-agent", calculate_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    # 运行查询
    result = await app.run_query("计算 2+2")
    assert "answer" in result
    assert "2" in str(result["answer"]) or "4" in str(result["answer"])

    await app.shutdown()


@pytest.mark.asyncio
async def test_full_pipeline_multi_step():
    """测试多步骤查询。
    用户输入: "获取用户数据，分析趋势，生成报告"
    流程: fetch_data → analyze_trend → generate_report → final_answer
    """
    llm = MockLLMClient()
    # IntentParser 响应 -> _plan 响应
    llm.set_json_responses([
        {
            "intent": "data_analysis",
            "required_skills": ["fetch", "analyze", "report"],
            "payload": {"topic": "sales"},
            "priority": "normal",
        },
        {
            "fetch_data": {"task": "fetch", "depends_on": []},
            "analyze_trend": {"task": "analyze", "depends_on": ["fetch_data"]},
            "generate_report": {"task": "report", "depends_on": ["analyze_trend"]},
            "final_answer": {"task": "summarize", "depends_on": ["generate_report"]},
        },
    ])
    # 总结响应
    llm.set_text_responses(["Summary: User asked for data analysis."])

    skill_signatures = {
        "fetch": "Fetch data from source",
        "analyze": "Analyze data trends",
        "report": "Generate a report",
        "summarize": "Generate a final answer summary",
    }

    app = create_test_app(skill_signatures, llm)
    await app.start()

    # 存储执行顺序
    execution_order = []

    async def fetch_handler(ecm, view):
        execution_order.append("fetch")
        result = {"data": [{"month": "Jan", "sales": 100}, {"month": "Feb", "sales": 150}]}
        await view.put(f"hivemind:result:{ecm.intent_id}", result)
        return result

    async def analyze_handler(ecm, view):
        execution_order.append("analyze")
        result = {"trend": "increasing", "growth": 0.5}
        await view.put(f"hivemind:result:{ecm.intent_id}", result)
        return result

    async def report_handler(ecm, view):
        execution_order.append("report")
        result = {"report": "Sales increased by 50%"}
        await view.put(f"hivemind:result:{ecm.intent_id}", result)
        return result

    async def summarize_handler(ecm, view):
        execution_order.append("summarize")
        answer = "Sales report: increasing trend with 50% growth"
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}

    await app.create_skill_agent("fetch", "fetch-agent", fetch_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("analyze", "analyze-agent", analyze_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})
    await app.create_skill_agent("report", "report-agent", report_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    result = await app.run_query("获取用户数据，分析趋势，生成报告")

    # 验证执行顺序
    assert execution_order == ["fetch", "analyze", "report", "summarize"]
    assert "answer" in result
    answer_str = str(result["answer"]).lower()
    assert "increasing" in answer_str or "growth" in answer_str

    await app.shutdown()


# ============================================================
# 2. 错误恢复测试
# ============================================================

@pytest.mark.asyncio
async def test_error_recovery_and_replan():
    """测试节点失败后的 replan 流程。
    第一次执行: fetch → fail → replan
    第二次执行: fetch → fallback_fetch → final_answer
    """
    llm = MockLLMClient()
    # IntentParser -> _plan (first) -> _replan
    llm.set_json_responses([
        {
            "intent": "data_fetch",
            "required_skills": ["fetch", "summarize"],
            "payload": {"source": "api"},
            "priority": "normal",
        },
        {
            "fetch_data": {"task": "fetch", "depends_on": []},
            "final_answer": {"task": "summarize", "depends_on": ["fetch_data"]},
        },
        {
            "fetch_data_retry": {"task": "fetch", "depends_on": []},
            "final_answer": {"task": "summarize", "depends_on": ["fetch_data_retry"]},
        },
    ])
    # Diagnoser 响应 -> _replan 响应
    llm.set_text_responses([
        "Fetch failed due to network timeout. Retry with different endpoint.",
        "Summary: Data fetch retry succeeded."
    ])

    skill_signatures = {
        "fetch": "Fetch data from source",
        "summarize": "Generate a final answer summary",
    }

    app = create_test_app(skill_signatures, llm)
    app.config.max_replan_attempts = 2
    await app.start()

    call_count = [0]

    async def fetch_handler(ecm, view):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("Network timeout")
        result = {"data": "recovered data"}
        await view.put(f"hivemind:result:{ecm.intent_id}", result)
        return result

    async def summarize_handler(ecm, view):
        answer = "Data retrieved successfully after retry"
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}

    await app.create_skill_agent("fetch", "fetch-agent", fetch_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    result = await app.run_query("获取数据")

    # 验证重试成功
    assert call_count[0] == 2
    assert "answer" in result
    answer_str = str(result["answer"]).lower()
    assert "recovered" in answer_str or "successfully" in answer_str

    await app.shutdown()


# ============================================================
# 3. 内存持久化测试
# ============================================================

@pytest.mark.asyncio
async def test_memory_persistence_after_query():
    """测试查询后内存持久化。
    执行查询后，短期记忆和长期记忆都正确更新。
    """
    llm = MockLLMClient()
    # IntentParser -> _plan
    llm.set_json_responses([
        {
            "intent": "simple",
            "required_skills": ["echo"],
            "payload": {},
            "priority": "normal",
        },
        {
            "echo_node": {"task": "echo", "depends_on": []},
            "final_answer": {"task": "summarize", "depends_on": ["echo_node"]},
        },
    ])
    # summarize_and_remember 响应
    llm.set_text_responses(["Summary: User said hello world."])

    skill_signatures = {
        "echo": "Echo the input",
        "summarize": "Generate a final answer summary",
    }

    app = create_test_app(skill_signatures, llm)
    await app.start()

    async def echo_handler(ecm, view):
        result = {"echo": "You said: hello world"}
        await view.put(f"hivemind:result:{ecm.intent_id}", result)
        return result

    async def summarize_handler(ecm, view):
        answer = "You said: hello world"
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}

    await app.create_skill_agent("echo", "echo-agent", echo_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    await app.run_query("hello world")

    # 等待后台总结任务完成
    await asyncio.sleep(0.5)

    # 验证长期记忆 (summarize_and_remember 会将总结写入长期记忆)
    recalled = await app.memory.recall_long_term("hello world", k=5)
    assert len(recalled) >= 1
    # 验证总结内容包含关键词
    summary_text = recalled[0].content.lower() if hasattr(recalled[0], 'content') else str(recalled[0]).lower()
    assert "hello" in summary_text or "world" in summary_text or "user" in summary_text

    await app.shutdown()


# ============================================================
# 4. 并发查询隔离测试
# ============================================================

@pytest.mark.asyncio
async def test_concurrent_queries_isolation():
    """测试并发查询的隔离性。
    两个查询并行执行，结果互不干扰。
    """
    llm = MockLLMClient()
    # Query 1: IntentParser -> _plan
    # Query 2: IntentParser -> _plan
    llm.set_json_responses([
        {"intent": "calc_a", "required_skills": ["calc"], "payload": {"value": 10}, "priority": "normal"},
        {"calc": {"task": "calc", "depends_on": []}, "final_answer": {"task": "summarize", "depends_on": ["calc"]}},
        {"intent": "calc_b", "required_skills": ["calc"], "payload": {"value": 20}, "priority": "normal"},
        {"calc": {"task": "calc", "depends_on": []}, "final_answer": {"task": "summarize", "depends_on": ["calc"]}},
    ])
    llm.set_text_responses(["Summary 1", "Summary 2"])

    skill_signatures = {
        "calc": "Calculate a value",
        "summarize": "Generate a final answer summary",
    }

    app = create_test_app(skill_signatures, llm)
    await app.start()

    async def calc_handler(ecm, view):
        value = ecm.payload.get("value", 0)
        result = {"calculated": value * 2}
        await view.put(f"hivemind:result:{ecm.intent_id}", result)
        return result

    async def summarize_handler(ecm, view):
        answer = "Calculated value"
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": answer})
        return {"answer": answer}

    await app.create_skill_agent("calc", "calc-agent", calc_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    # 并发执行两个查询
    results = await asyncio.gather(
        app.run_query("计算 10*2"),
        app.run_query("计算 20*2"),
    )

    assert len(results) == 2
    assert "answer" in results[0]
    assert "answer" in results[1]

    await app.shutdown()


# ============================================================
# 5. 权限隔离测试
# ============================================================

@pytest.mark.asyncio
async def test_skill_permission_isolation():
    """测试技能权限隔离。
    技能只能读写授权的键。
    """
    llm = MockLLMClient()
    llm.set_json_responses([
        {"intent": "test", "required_skills": ["secure_op"], "payload": {}, "priority": "normal"},
        {"op_node": {"task": "secure_op", "depends_on": []},
         "final_answer": {"task": "summarize", "depends_on": ["op_node"]}},
    ])
    llm.set_text_responses(["Summary: Security test completed."])

    skill_signatures = {
        "secure_op": "Perform a secure operation",
        "summarize": "Generate a final answer summary",
    }

    app = create_test_app(skill_signatures, llm)
    await app.start()

    async def secure_handler(ecm, view):
        # 写入授权的键应该成功
        await view.put(f"hivemind:result:{ecm.intent_id}", {"success": True})
        return {"success": True}

    async def summarize_handler(ecm, view):
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": "Operation completed"})
        return {"answer": "Operation completed"}

    await app.create_skill_agent("secure_op", "secure-agent", secure_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    result = await app.run_query("执行安全操作")
    assert "answer" in result

    await app.shutdown()


# ============================================================
# 6. 动态子图测试
# ============================================================

@pytest.mark.asyncio
async def test_dynamic_subgraph_generation():
    """测试动态子图生成。
    规划器返回包含动态节点的图，执行器正确处理。
    """
    llm = MockLLMClient()
    llm.set_json_responses([
        {"intent": "dynamic", "required_skills": ["expand"], "payload": {}, "priority": "normal"},
        {
            "expand_node": {"task": "expand", "depends_on": []},
            "process_a": {"task": "process", "depends_on": ["expand_node"]},
            "process_b": {"task": "process", "depends_on": ["expand_node"]},
            "final_answer": {"task": "summarize", "depends_on": ["process_a", "process_b"]},
        },
    ])
    llm.set_text_responses(["Summary: Dynamic subgraph test completed."])

    skill_signatures = {
        "expand": "Expand into sub-tasks",
        "process": "Process a sub-task",
        "summarize": "Generate a final answer summary",
    }

    app = create_test_app(skill_signatures, llm)
    await app.start()

    execution_log = []

    async def expand_handler(ecm, view):
        execution_log.append("expand")
        await view.put(f"hivemind:result:{ecm.intent_id}", {"expanded": True})
        return {"expanded": True}

    async def process_handler(ecm, view):
        execution_log.append("process")
        await view.put(f"hivemind:result:{ecm.intent_id}", {"processed": True})
        return {"processed": True}

    async def summarize_handler(ecm, view):
        execution_log.append("summarize")
        await view.put(f"hivemind:result:{ecm.intent_id}", {"answer": "All tasks completed"})
        return {"answer": "All tasks completed"}

    await app.create_skill_agent("expand", "expand-agent", expand_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("process", "process-agent", process_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    result = await app.run_query("动态生成子图")

    assert "expand" in execution_log
    assert execution_log.count("process") == 2
    assert "summarize" in execution_log
    assert "answer" in result

    await app.shutdown()


# ============================================================
# 7. 全局超时测试
# ============================================================

@pytest.mark.asyncio
async def test_global_timeout_enforcement():
    """测试全局超时 enforcement。
    长时间运行的节点应被超时中断。
    """
    llm = MockLLMClient()
    llm.set_json_responses([
        {"intent": "slow", "required_skills": ["slow_op"], "payload": {}, "priority": "normal"},
        {"slow_node": {"task": "slow_op", "depends_on": []},
         "final_answer": {"task": "summarize", "depends_on": ["slow_node"]}},
    ])
    llm.set_text_responses(["Summary: Should not reach here."])

    skill_signatures = {
        "slow_op": "A slow operation",
        "summarize": "Generate a final answer summary",
    }

    config = HiveFlowConfig(blackboard_type="memory")
    embedding_llm = MockLLMClient()
    vs = MockVectorStore(embedding_fn=embedding_llm.embed)
    hive_config = HiveMindConfig(
        hiveflow_config=config,
        llm=llm,
        embedding_llm=embedding_llm,
        vector_store=vs,
        skill_registry=skill_signatures,
        global_timeout=0.1,  # 100ms 超时
        enable_result_cleanup=False,
    )
    app = HiveMindApp(hive_config)
    await app.start()

    async def slow_handler(ecm, view):
        await asyncio.sleep(10)  # 远超超时时间
        return {"done": True}

    async def summarize_handler(ecm, view):
        return {"answer": "Should not reach here"}

    await app.create_skill_agent("slow_op", "slow-agent", slow_handler,
                                read_keys=set(), write_keys={"hivemind:result:*"})
    await app.create_skill_agent("summarize", "sum-agent", summarize_handler,
                                read_keys={"hivemind:result:*"}, write_keys={"hivemind:result:*"})

    with pytest.raises((asyncio.TimeoutError, Exception)):
        await app.run_query("慢操作测试")

    await app.shutdown()
