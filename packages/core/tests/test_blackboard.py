import pytest
import asyncio
from hiveflow import MemoryBlackboard, TTLMemoryBlackboard


@pytest.fixture
def blackboard():
    return MemoryBlackboard()


@pytest.fixture
def ttl_blackboard():
    return TTLMemoryBlackboard()


@pytest.mark.asyncio
async def test_basic_put_get(blackboard):
    await blackboard.put("key1", "value1")
    result = await blackboard.get("key1")
    assert result == "value1"


@pytest.mark.asyncio
async def test_key_error_on_missing(blackboard):
    with pytest.raises(KeyError):
        await blackboard.get("nonexistent")


@pytest.mark.asyncio
async def test_delete(blackboard):
    await blackboard.put("key1", "value1")
    await blackboard.delete("key1")
    with pytest.raises(KeyError):
        await blackboard.get("key1")


@pytest.mark.asyncio
async def test_wait_for_key(blackboard):
    async def setter():
        await asyncio.sleep(0.05)
        await blackboard.put("key2", "value2")

    asyncio.create_task(setter())
    result = await blackboard.wait_for_key("key2", timeout=1.0)
    assert result == "value2"


@pytest.mark.asyncio
async def test_wait_timeout(blackboard):
    with pytest.raises(KeyError):
        await blackboard.wait_for_key("never_exists", timeout=0.1)


@pytest.mark.asyncio
async def test_ttl_expiration(ttl_blackboard):
    await ttl_blackboard.put("ttl_key", "temp_value", ttl=0.1)
    result = await ttl_blackboard.get("ttl_key")
    assert result == "temp_value"
    await asyncio.sleep(0.15)
    with pytest.raises(KeyError):
        await ttl_blackboard.get("ttl_key")


@pytest.mark.asyncio
async def test_complex_values(blackboard):
    data = {"nested": {"list": [1, 2, 3]}, "flag": True}
    await blackboard.put("complex", data)
    result = await blackboard.get("complex")
    assert result == data
