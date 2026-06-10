"""HiveFlow Core - SecureBlackboard and ensure_error_writes tests"""
import pytest
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import (
    SecureBlackboard, MemoryBlackboard, Capability,
    ensure_error_writes, ECM, Expectation,
    InProcessEventBus, AuditedBlackboardView
)


@pytest.fixture
def backend():
    return MemoryBlackboard()


@pytest.fixture
def blackboard(backend):
    return SecureBlackboard(backend)


# ========== SecureBlackboard JSON Serialization Check ==========

@pytest.mark.asyncio
async def test_json_serializable_value_accepted(blackboard):
    """正常 JSON 可序列化的值应该被接受"""
    await blackboard.sys_put("key1", {"data": "test", "number": 42})
    result = await blackboard.sys_get("key1")
    assert result["data"] == "test"


@pytest.mark.asyncio
async def test_non_json_value_rejected_sys_put(blackboard):
    """非 JSON 可序列化的值（如 set）应该被 sys_put 拒绝"""
    with pytest.raises(ValueError, match="not JSON-serializable"):
        await blackboard.sys_put("key_bad", {1, 2, 3})


@pytest.mark.asyncio
async def test_non_json_value_rejected_put_and_audit(blackboard):
    """非 JSON 可序列化的值应该被 put_and_audit 拒绝"""
    cap = Capability(
        agent_id="agent1",
        skills={"test"},
        read_keys={"*"},
        write_keys={"*"},
    )
    await blackboard.register_agent("agent1", cap)

    with pytest.raises(ValueError, match="not JSON-serializable"):
        await blackboard.put_and_audit("agent1", "bad_key", {1, 2, 3})


@pytest.mark.asyncio
async def test_valid_value_accepted_put_and_audit(blackboard):
    """正常值应该通过 put_and_audit"""
    cap = Capability(
        agent_id="agent2",
        skills={"test"},
        read_keys={"*"},
        write_keys={"data.*"},
    )
    await blackboard.register_agent("agent2", cap)

    await blackboard.put_and_audit("agent2", "data.result", {"value": 123})
    result = await blackboard.sys_get("data.result")
    assert result["value"] == 123


@pytest.mark.asyncio
async def test_custom_object_rejected(blackboard):
    """自定义对象（非 JSON 序列化）应该被拒绝"""
    class MyObject:
        pass

    with pytest.raises(ValueError, match="not JSON-serializable"):
        await blackboard.sys_put("obj_key", MyObject())


# ========== SecureBlackboard Permission Checks ==========

@pytest.mark.asyncio
async def test_unregistered_agent_cannot_write(blackboard):
    """未注册的 Agent 不能写入"""
    with pytest.raises(PermissionError, match="not registered"):
        await blackboard.put_and_audit("unknown", "key", "value")


@pytest.mark.asyncio
async def test_read_permission_check(blackboard):
    """Agent 不能读取没有权限的 key"""
    cap = Capability(
        agent_id="limited",
        skills={"test"},
        read_keys={"allowed.*"},
        write_keys={"allowed.*"},
    )
    await blackboard.register_agent("limited", cap)
    await blackboard.sys_put("forbidden.key", "secret")

    with pytest.raises(PermissionError, match="lacks read permission"):
        await blackboard.get_and_audit("limited", "forbidden.key")


@pytest.mark.asyncio
async def test_write_permission_check(blackboard):
    """Agent 不能写入没有权限的 key"""
    cap = Capability(
        agent_id="writer",
        skills={"test"},
        read_keys={"*"},
        write_keys={"allowed.*"},
    )
    await blackboard.register_agent("writer", cap)

    with pytest.raises(PermissionError, match="lacks write permission"):
        await blackboard.put_and_audit("writer", "forbidden.key", "value")


@pytest.mark.asyncio
async def test_wildcard_permission(blackboard):
    """通配符权限应该生效"""
    cap = Capability(
        agent_id="wild",
        skills={"test"},
        read_keys={"data/*"},
        write_keys={"data/*"},
    )
    await blackboard.register_agent("wild", cap)

    await blackboard.put_and_audit("wild", "data/report", {"ok": True})
    result = await blackboard.get_and_audit("wild", "data/report")
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_audit_log_records_actions(blackboard):
    """审计日志应该记录所有操作"""
    cap = Capability(
        agent_id="auditor",
        skills={"test"},
        read_keys={"audit.*"},
        write_keys={"audit.*"},
    )
    await blackboard.register_agent("auditor", cap)

    await blackboard.put_and_audit("auditor", "audit.test", {"data": 1})
    await blackboard.get_and_audit("auditor", "audit.test")

    audit = blackboard._audit_log
    put_entries = [e for e in audit if e["action"] == "put" and e["agent"] == "auditor"]
    get_entries = [e for e in audit if e["action"] == "get" and e["agent"] == "auditor"]
    assert len(put_entries) >= 1
    assert len(get_entries) >= 1


# ========== ensure_error_writes ==========

@pytest.mark.asyncio
async def test_ensure_error_writes_catches_exception(blackboard):
    """ensure_error_writes 应该在任务失败时自动写入错误到黑板"""
    ecm = ECM(
        trace_id="trace-1",
        intent="test.intent",
        intent_id="intent-123",
        emitter="test_agent",
        payload={"data": "test"}
    )

    cap = Capability(
        agent_id="test_agent",
        skills={"test"},
        read_keys={"*"},
        write_keys={"*"},
    )
    await blackboard.register_agent("test_agent", cap)
    view = blackboard.view_for("test_agent")

    @ensure_error_writes(blackboard, "test_agent")
    async def failing_handler(ecm: ECM, view: AuditedBlackboardView):
        raise ValueError("Something went wrong")

    with pytest.raises(ValueError, match="Something went wrong"):
        await failing_handler(ecm, view)

    # 验证错误已写入黑板
    error_key = "error.intent-123.test_agent"
    error_data = await blackboard.sys_get(error_key)
    assert "Something went wrong" in error_data["error"]
    assert error_data["intent_id"] == "intent-123"
    assert error_data["agent_id"] == "test_agent"
    assert "traceback" in error_data


@pytest.mark.asyncio
async def test_ensure_error_writes_passes_on_success(blackboard):
    """成功时 ensure_error_writes 不应该写入错误"""
    ecm = ECM(
        trace_id="trace-2",
        intent="test.success",
        intent_id="intent-ok",
        emitter="ok_agent",
        payload={"data": "test"}
    )

    cap = Capability(
        agent_id="ok_agent",
        skills={"test"},
        read_keys={"*"},
        write_keys={"*"},
    )
    await blackboard.register_agent("ok_agent", cap)
    view = blackboard.view_for("ok_agent")

    @ensure_error_writes(blackboard, "ok_agent")
    async def success_handler(ecm: ECM, view: AuditedBlackboardView):
        return {"result": "success"}

    result = await success_handler(ecm, view)
    assert result["result"] == "success"

    # 验证没有错误被写入
    error_key = "error.intent-ok.ok_agent"
    with pytest.raises(KeyError):
        await blackboard.sys_get(error_key)


@pytest.mark.asyncio
async def test_ensure_error_writes_preserves_exception_type(blackboard):
    """ensure_error_writes 应该保持原始异常类型"""
    ecm = ECM(
        trace_id="trace-3",
        intent="test.type",
        intent_id="intent-type",
        emitter="type_agent",
        payload={}
    )

    cap = Capability(
        agent_id="type_agent",
        skills={"test"},
        read_keys={"*"},
        write_keys={"*"},
    )
    await blackboard.register_agent("type_agent", cap)
    view = blackboard.view_for("type_agent")

    @ensure_error_writes(blackboard, "type_agent")
    async def type_handler(ecm: ECM, view: AuditedBlackboardView):
        raise RuntimeError("Runtime failure")

    with pytest.raises(RuntimeError, match="Runtime failure"):
        await type_handler(ecm, view)
