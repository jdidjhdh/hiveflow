import pytest
import asyncio
from core.secure_blackboard import SecureBlackboard, MemoryBlackboard, Capability


@pytest.fixture
def blackboard():
    return SecureBlackboard(MemoryBlackboard())


@pytest.fixture
def agent_cap():
    return Capability(
        agent_id="agent1",
        skills={"read_data", "write_result"},
        read_keys={"data:*"},
        write_keys={"result:*"}
    )


@pytest.mark.asyncio
async def test_register_and_use(blackboard, agent_cap):
    await blackboard.register_agent("agent1", agent_cap)
    await blackboard.sys_put("data:test", {"value": 42})
    val = await blackboard.get_and_audit("agent1", "data:test")
    assert val == {"value": 42}


@pytest.mark.asyncio
async def test_permission_denied_read(blackboard, agent_cap):
    await blackboard.register_agent("agent1", agent_cap)
    await blackboard.sys_put("forbidden:key", "secret")
    with pytest.raises(PermissionError):
        await blackboard.get_and_audit("agent1", "forbidden:key")


@pytest.mark.asyncio
async def test_permission_denied_write(blackboard, agent_cap):
    await blackboard.register_agent("agent1", agent_cap)
    with pytest.raises(PermissionError):
        await blackboard.put_and_audit("agent1", "forbidden:key", "value")


@pytest.mark.asyncio
async def test_unregistered_agent(blackboard):
    with pytest.raises(PermissionError):
        await blackboard.get_and_audit("unknown", "data:test")


@pytest.mark.asyncio
async def test_wildcard_rejected(blackboard, agent_cap):
    agent_cap.read_keys = {"*"}
    await blackboard.register_agent("agent1", agent_cap)
    with pytest.raises(PermissionError, match="Wildcard"):
        await blackboard.get_and_audit("agent1", "any:key")


@pytest.mark.asyncio
async def test_audit_log(blackboard, agent_cap):
    await blackboard.register_agent("agent1", agent_cap)
    await blackboard.sys_put("data:test", "value")
    await blackboard.get_and_audit("agent1", "data:test")
    await blackboard.put_and_audit("agent1", "result:test", "output")
    assert len(blackboard._audit_log) == 2


@pytest.mark.asyncio
async def test_non_json_serializable(blackboard, agent_cap):
    await blackboard.register_agent("agent1", agent_cap)
    with pytest.raises(ValueError, match="not JSON serializable"):
        await blackboard.put_and_audit("agent1", "result:bad", set())
