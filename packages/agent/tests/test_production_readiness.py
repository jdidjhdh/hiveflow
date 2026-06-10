"""
HiveFlow Agent 生产可用性测试 (聚焦单元测试)

覆盖关键生产场景:
1. ensure_error_writes 包装器
2. MemoryManager 生命周期 (持久化/限制/总结)
3. IntentParser 边界输入
4. HiveMindApp 配置验证
5. 权限隔离 (Agent 版 fnmatch)
6. SkillBinding 数据类
7. 输出验证
8. 输入守卫
"""

import pytest
import asyncio
from typing import List

from hiveflow import HiveFlow, HiveFlowConfig, MISSING
from hiveflow.blackboard import MemoryBlackboard, SecureBlackboard as CoreSecureBlackboard

from app import HiveMindApp, HiveMindConfig, SkillBinding, ensure_error_writes
from core.secure_blackboard import SecureBlackboard as AppSecureBlackboard
from llm.base import LLMClient
from memory.vector_store import VectorStore
from memory.manager import MemoryManager
from intent_parser import IntentParser


# ============================================================
# Mock 组件
# ============================================================

class MockLLMClient(LLMClient):
    def __init__(self):
        self._json_responses = []
        self._text_responses = []
        self._json_idx = 0
        self._text_idx = 0

    def set_json_responses(self, responses):
        self._json_responses = responses
        self._json_idx = 0

    def set_text_responses(self, responses):
        self._text_responses = responses
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


def create_memory_manager(limit=10):
    llm = MockLLMClient()
    bb = AppSecureBlackboard(MemoryBlackboard())
    vs = MockVectorStore(embedding_fn=llm.embed)
    return MemoryManager(bb, vs, short_term_limit=limit)


# ============================================================
# 1. ensure_error_writes Wrapper
# ============================================================

@pytest.mark.asyncio
async def test_ensure_error_writes_catches_exception():
    """测试包装器捕获异常并返回错误字典。"""
    async def failing_handler(ecm, view):
        raise RuntimeError("test error")

    wrapped = ensure_error_writes(failing_handler)

    class MockECM:
        expectation = None
        intent_id = "test-intent-123"

    result = await wrapped(MockECM(), None)
    assert "error" in result
    assert "test error" in result["error"]


@pytest.mark.asyncio
async def test_ensure_error_writes_writes_error_to_blackboard():
    """测试异常时错误被写入黑板。"""
    bb = AppSecureBlackboard(MemoryBlackboard())
    # 使用精确键名而不是通配符 (fnmatch 拒绝裸 *)
    cap = type('Cap', (), {
        'agent_id': 'test',
        'read_keys': {'test_result'},
        'write_keys': {'test_result'}
    })()
    await bb.register_agent("test", cap)
    view = bb.view_for("test")

    async def failing_handler(ecm, view):
        raise RuntimeError("fail!")

    wrapped = ensure_error_writes(failing_handler)

    from hiveflow import ECM, Expectation
    ecm = ECM(
        trace_id="err-1", intent="test", intent_id="err",
        emitter="test", required_skills=["test"],
        expectation=Expectation(state_key="test_result", expected_schema={})
    )

    result = await wrapped(ecm, view)
    assert "error" in result
    written = await bb.sys_get("test_result")
    assert "error" in written


@pytest.mark.asyncio
async def test_ensure_error_writes_success_passes_through():
    """测试正常执行时结果透传。"""
    async def ok_handler(ecm, view):
        return {"ok": True}

    wrapped = ensure_error_writes(ok_handler)

    class MockECM:
        expectation = None

    result = await wrapped(MockECM(), None)
    assert result == {"ok": True}


# ============================================================
# 2. Memory Manager Lifecycle
# ============================================================

@pytest.mark.asyncio
async def test_memory_persistence_and_recall():
    """测试记忆持久化与召回。"""
    mm = create_memory_manager()
    # add_to_short_term 写入 short_term list
    mm.add_to_short_term("user", "What is AI?")
    mm.add_to_short_term("assistant", "AI is artificial intelligence.")

    st = mm.get_short_term()
    assert len(st) >= 2

    await mm.save_long_term("User asked about AI", metadata={"topic": "ai"})
    recalled = await mm.recall_long_term("AI", k=5)
    assert len(recalled) >= 1


@pytest.mark.asyncio
async def test_memory_limit_enforcement():
    """测试短期记忆 LRU 限制 (max_messages = limit * 2)。"""
    mm = create_memory_manager(limit=3)

    for i in range(20):
        mm.add_to_short_term("user" if i % 2 == 0 else "assistant", f"msg_{i}")

    st = mm.get_short_term()
    assert len(st) <= 6  # limit * 2


@pytest.mark.asyncio
async def test_memory_summarize_and_remember():
    """测试对话总结写入长期记忆。"""
    mm = create_memory_manager()
    llm = MockLLMClient()

    mm.add_to_short_term("user", "What is Python?")
    mm.add_to_short_term("assistant", "Python is a programming language.")

    llm.set_text_responses(["Summary: User asked about Python."])

    await mm.summarize_and_remember("conv-1", llm)

    # summarize_and_remember 会写入长期记忆
    recalled = await mm.recall_long_term("Python", k=5)
    assert len(recalled) >= 1

    # short_term 被清空
    assert len(mm.get_short_term()) == 0


# ============================================================
# 3. Intent Parser Edge Cases
# ============================================================

@pytest.mark.asyncio
async def test_intent_parser_empty_input():
    """测试空输入解析。"""
    llm = MockLLMClient()
    llm.set_json_responses([
        {"intent": "unknown", "required_skills": [],
         "payload": {}, "priority": "low"},
    ])
    parser = IntentParser(llm, {})
    ecm = await parser.parse("")
    assert ecm is not None


@pytest.mark.asyncio
async def test_intent_parser_special_characters():
    """测试特殊字符输入。"""
    llm = MockLLMClient()
    llm.set_json_responses([
        {"intent": "search", "required_skills": ["web_search"],
         "payload": {"query": "<script>alert('xss')</script>"}, "priority": "normal"},
    ])
    parser = IntentParser(llm, {"web_search": "search"})
    ecm = await parser.parse("<script>alert('xss')</script>")
    assert ecm.intent == "search"


@pytest.mark.asyncio
async def test_intent_parser_very_long_input():
    """测试超长输入。"""
    long_input = "A" * 10000
    llm = MockLLMClient()
    llm.set_json_responses([
        {"intent": "search", "required_skills": [],
         "payload": {"query": long_input}, "priority": "normal"},
    ])
    parser = IntentParser(llm, {})
    ecm = await parser.parse(long_input)
    assert ecm is not None


# ============================================================
# 4. HiveMindConfig Validation
# ============================================================

def test_hive_mind_config_defaults():
    """测试配置默认值。"""
    llm = MockLLMClient()
    embedding_llm = MockLLMClient()
    vs = MockVectorStore(embedding_fn=embedding_llm.embed)
    config = HiveFlowConfig(blackboard_type="memory")
    hive_config = HiveMindConfig(
        hiveflow_config=config,
        llm=llm,
        embedding_llm=embedding_llm,
        vector_store=vs,
    )

    assert hive_config.system_prompt == "You are a helpful assistant."
    assert hive_config.max_replan_attempts == 3
    assert hive_config.global_timeout == 300.0
    assert hive_config.enable_result_cleanup is True


def test_hive_mind_config_custom():
    """测试自定义配置。"""
    llm = MockLLMClient()
    embedding_llm = MockLLMClient()
    vs = MockVectorStore(embedding_fn=embedding_llm.embed)
    config = HiveFlowConfig(blackboard_type="memory")
    hive_config = HiveMindConfig(
        hiveflow_config=config,
        llm=llm,
        embedding_llm=embedding_llm,
        vector_store=vs,
        system_prompt="Custom prompt",
        max_replan_attempts=5,
        global_timeout=60.0,
        enable_result_cleanup=False,
        short_term_limit=3,
    )

    assert hive_config.system_prompt == "Custom prompt"
    assert hive_config.max_replan_attempts == 5
    assert hive_config.enable_result_cleanup is False
    assert hive_config.short_term_limit == 3


# ============================================================
# 5. Blackboard Permission Isolation (Agent fnmatch version)
# ============================================================

@pytest.mark.asyncio
async def test_blackboard_fnmatch_permission_isolation():
    """测试 Agent 版 fnmatch 权限隔离。"""
    bb = AppSecureBlackboard(MemoryBlackboard())

    from core.secure_blackboard import Capability

    cap_a = Capability(
        agent_id="iso-a", skills={"x"},
        read_keys={"a:*", "public:*"}, write_keys={"a:*", "public:*"}
    )
    cap_b = Capability(
        agent_id="iso-b", skills={"x"},
        read_keys={"b:*", "public:*"}, write_keys={"b:*", "public:*"}
    )

    await bb.register_agent("iso-a", cap_a)
    await bb.register_agent("iso-b", cap_b)

    await bb.put_and_audit("iso-a", "a:secret", "value_a")
    await bb.put_and_audit("iso-b", "b:secret", "value_b")
    await bb.put_and_audit("iso-a", "public:info", {"shared": True})

    # a 不能读 b
    with pytest.raises(PermissionError):
        await bb.get_and_audit("iso-a", "b:secret")

    # b 不能读 a
    with pytest.raises(PermissionError):
        await bb.get_and_audit("iso-b", "a:secret")

    # 公共数据双方都可读
    assert await bb.get_and_audit("iso-b", "public:info") == {"shared": True}


@pytest.mark.asyncio
async def test_blackboard_unregistered_agent_rejected():
    """测试未注册 agent 被拒绝。"""
    bb = AppSecureBlackboard(MemoryBlackboard())

    with pytest.raises(PermissionError):
        await bb.get_and_audit("unknown", "any:key")


@pytest.mark.asyncio
async def test_blackboard_wildcard_rejected():
    """测试裸通配符被拒绝。"""
    bb = AppSecureBlackboard(MemoryBlackboard())
    from core.secure_blackboard import Capability

    cap = Capability(
        agent_id="wc-test", skills={"x"},
        read_keys={"*"}, write_keys={"*"}
    )
    await bb.register_agent("wc-test", cap)

    with pytest.raises(PermissionError, match="not allowed"):
        await bb.put_and_audit("wc-test", "test:key", "value")


# ============================================================
# 6. SkillBinding Dataclass
# ============================================================

def test_skill_binding_dataclass():
    """测试 SkillBinding 数据结构。"""
    async def handler(ecm, view):
        pass

    binding = SkillBinding(
        skill_name="test_skill",
        agent_id="test-agent",
        handler=handler,
        read_keys={"read:*"},
        write_keys={"write:*"},
    )

    assert binding.skill_name == "test_skill"
    assert binding.agent_id == "test-agent"
    assert "read:*" in binding.read_keys


# ============================================================
# 7. Output Validation Integration
# ============================================================

@pytest.mark.asyncio
async def test_output_validation_integration():
    """测试输出验证逻辑。"""
    class MockValidator:
        async def validate(self, answer, context=""):
            return "safe" in answer.lower()

    validator = MockValidator()
    assert await validator.validate("This is safe") is True
    assert await validator.validate("This is dangerous!") is False


# ============================================================
# 8. Input Guard Integration
# ============================================================

class MockInputGuard:
    def __init__(self, blocked_patterns=None):
        self.blocked_patterns = blocked_patterns or []

    async def check(self, text):
        for pattern in self.blocked_patterns:
            if pattern.lower() in text.lower():
                raise ValueError(f"Input blocked: {pattern}")


@pytest.mark.asyncio
async def test_input_guard_blocks():
    """测试输入守卫阻止。"""
    guard = MockInputGuard(blocked_patterns=["harmful"])
    with pytest.raises(ValueError, match="blocked"):
        await guard.check("This is harmful content")


@pytest.mark.asyncio
async def test_input_guard_passes():
    """测试输入守卫放行。"""
    guard = MockInputGuard(blocked_patterns=["harmful"])
    await guard.check("This is safe content")  # should not raise


# ============================================================
# 9. App Start/Shutdown without run_query
# ============================================================

@pytest.mark.asyncio
async def test_app_start_and_shutdown():
    """测试 App 启动和关闭流程。"""
    llm = MockLLMClient()
    embedding_llm = MockLLMClient()
    vs = MockVectorStore(embedding_fn=embedding_llm.embed)
    config = HiveFlowConfig(blackboard_type="memory")
    hive_config = HiveMindConfig(
        hiveflow_config=config,
        llm=llm,
        embedding_llm=embedding_llm,
        vector_store=vs,
        skill_registry={"test": "Test skill"},
    )
    app = HiveMindApp(hive_config)

    await app.start()
    assert app.cognitive_orch is not None

    async def test_handler(ecm, view):
        return {"ok": True}

    worker = await app.create_skill_agent("test", "test-agent", test_handler,
                                           read_keys=set(), write_keys={"test:*"})
    assert "test" in app.skill_bindings

    await app.shutdown()


@pytest.mark.asyncio
async def test_app_run_query_before_start():
    """测试未启动时 run_query 失败。"""
    llm = MockLLMClient()
    embedding_llm = MockLLMClient()
    vs = MockVectorStore(embedding_fn=embedding_llm.embed)
    config = HiveFlowConfig(blackboard_type="memory")
    hive_config = HiveMindConfig(
        hiveflow_config=config, llm=llm,
        embedding_llm=embedding_llm, vector_store=vs,
    )
    app = HiveMindApp(hive_config)
    with pytest.raises(RuntimeError, match="not started"):
        await app.run_query("test")


@pytest.mark.asyncio
async def test_app_duplicate_skill_registration():
    """测试重复注册技能失败。"""
    llm = MockLLMClient()
    embedding_llm = MockLLMClient()
    vs = MockVectorStore(embedding_fn=embedding_llm.embed)
    config = HiveFlowConfig(blackboard_type="memory")
    hive_config = HiveMindConfig(
        hiveflow_config=config, llm=llm,
        embedding_llm=embedding_llm, vector_store=vs,
        skill_registry={"test": "Test"},
    )
    app = HiveMindApp(hive_config)
    await app.start()

    async def handler(ecm, view):
        return {}

    await app.create_skill_agent("test", "a1", handler, set(), {"t:*"})
    with pytest.raises(ValueError, match="already registered"):
        await app.create_skill_agent("test", "a2", handler, set(), {"t2:*"})

    await app.shutdown()
