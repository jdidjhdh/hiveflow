"""
HiveFlow 本地 LLM 容错回归测试

锁定两类真实场景修复（开源模型规划输出不稳定时的降级路径）：
1. Unknown skill 名回退：LLM 编造不存在技能时，节点映射到已注册技能且 task 名同步改写
2. replan 二次失败降级：重规划仍输出无效 TaskGraph 时，退化为基于已注册技能的链式图
"""
import pytest
import asyncio
from unittest.mock import AsyncMock

from hiveflow import HiveFlow, HiveFlowConfig
from core.secure_blackboard import SecureBlackboard, MemoryBlackboard
from memory.manager import MemoryManager
from intent_parser import IntentParser
from orchestrator.cognitive import CognitiveOrchestrator


class MockLLM:
    def __init__(self, json_responses=None):
        self.json_responses = json_responses or []
        self.idx = 0

    async def complete_json(self, messages, **kwargs):
        resp = self.json_responses[self.idx % len(self.json_responses)]
        self.idx += 1
        return resp

    async def complete(self, messages, **kwargs):
        return "ok"


class MockBinding:
    def __init__(self, skill_name):
        self.skill_name = skill_name
        self.agent_id = f"agent-{skill_name}"
        self.handler = AsyncMock(return_value={"result": "ok"})
        self.read_keys = set()
        self.write_keys = set()


def make_orch(bindings: dict, llm: MockLLM) -> CognitiveOrchestrator:
    hf = HiveFlow(HiveFlowConfig())
    memory = MemoryManager(SecureBlackboard(MemoryBlackboard()), None, short_term_limit=5)
    parser = IntentParser(llm, {})
    return CognitiveOrchestrator(
        llm=llm,
        hiveflow=hf,
        skill_bindings=bindings,
        skill_signatures={k: "desc" for k in bindings},
        memory_manager=memory,
        intent_parser=parser,
        max_replan_attempts=2,
    )


@pytest.mark.asyncio
async def test_unknown_skill_fallback_rewrites_task():
    """LLM 编造 skill 名时：不抛错、节点 task 被改写为已注册技能。"""
    bindings = {"analyze_data": MockBinding("analyze_data"), "summarize": MockBinding("summarize")}
    orch = make_orch(bindings, MockLLM())

    graph_spec = {
        "step1": {"task": "analyze_data", "depends_on": []},
        "final_answer": {"task": "noop", "depends_on": ["step1"]},  # LLM 编造 noop
    }

    executable = orch._build_executable_graph(graph_spec, "intent-1", "query", [], "", {}, {})
    assert "final_answer" in executable
    # task 被改写为 summarize（回退后闭包绑定的也是 summarize）
    assert graph_spec["final_answer"]["task"] == "summarize"


@pytest.mark.asyncio
async def test_unknown_skill_fallback_no_bindings_still_raises():
    """没有任何已注册技能时，回退无目标，仍按原逻辑抛错。"""
    orch = make_orch({}, MockLLM())
    graph_spec = {"node1": {"task": "unknown", "depends_on": []}}
    with pytest.raises(ValueError, match="Unknown skill"):
        orch._build_executable_graph(graph_spec, "intent-1", "query", [], "", {}, {})


@pytest.mark.asyncio
async def test_replan_double_failure_falls_back_to_skill_chain():
    """replan 二次输出无效图时：降级为基于已注册技能的链式图，不中断。"""
    # 两次 complete_json 都返回无效结构
    llm = MockLLM(json_responses=[{"not_a_graph": True}, {"still_invalid": 1}])
    bindings = {
        "analyze_data": MockBinding("analyze_data"),
        "summarize": MockBinding("summarize"),
    }
    orch = make_orch(bindings, llm)

    ecm = type("ECM", (), {
        "trace_id": "t1", "intent": "analyze", "intent_id": "i1",
        "required_skills": ["analyze_data"], "payload": {}, "priority": "normal",
        "user_query": "q", "conversation_id": "c",
    })()

    graph = await orch._replan(
        ecm,
        diagnosis="node failed",
        partial_results={},
        short_term=[],
        long_term_context="",
        intent_id="i1",
    )

    # 降级为链式图：step_1_analyze_data → step_2_summarize → final_answer
    assert "step_1_analyze_data" in graph
    assert graph["step_1_analyze_data"]["task"] == "analyze_data"
    assert graph["final_answer"]["task"] == "summarize"
    assert graph["final_answer"]["depends_on"] == ["step_2_summarize"]
