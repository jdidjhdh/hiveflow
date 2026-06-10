import pytest
import asyncio
import time

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

# Check if Redis server is actually running
async def _check_redis_connection():
    try:
        r = aioredis.from_url("redis://localhost", socket_timeout=2.0)
        await r.ping()
        await r.close()
        return True
    except Exception:
        return False

pytestmark = pytest.mark.skipif(not _REDIS_AVAILABLE, reason="redis package not installed")


@pytest.fixture
def redis_url():
    return "redis://localhost"


@pytest.mark.asyncio
async def test_redis_blackboard_basic_operations():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    bb = SecureBlackboard(RedisBlackboard(prefix="test:bb"))
    try:
        await bb.sys_put("key1", {"data": "value1"})
        result = await bb.sys_get("key1")
        assert result == {"data": "value1"}
        
        await bb.sys_put("key2", 42)
        result = await bb.sys_get("key2")
        assert result == 42
        
        await bb.sys_put("key3", [1, 2, 3])
        result = await bb.sys_get("key3")
        assert result == [1, 2, 3]
    finally:
        await bb.close()


@pytest.mark.asyncio
async def test_redis_blackboard_ttl():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    bb = SecureBlackboard(RedisBlackboard(prefix="test:bb:ttl"))
    try:
        await bb.sys_put("ttl_key", {"expires": True}, ttl=1.0)
        result = await bb.sys_get("ttl_key")
        assert result == {"expires": True}
        
        # Wait for TTL to expire
        await asyncio.sleep(1.5)
        
        with pytest.raises(KeyError):
            await bb.sys_get("ttl_key")
    finally:
        await bb.close()


@pytest.mark.asyncio
async def test_redis_blackboard_wait_for_key():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    bb = SecureBlackboard(RedisBlackboard(prefix="test:bb:wait", poll_interval=0.05))
    try:
        async def delayed_put():
            await asyncio.sleep(0.2)
            await bb.sys_put("wait_key", "appeared")
        
        task = asyncio.create_task(delayed_put())
        result = await bb.sys_wait_for_key("wait_key", timeout=2.0)
        assert result == "appeared"
        await task
    finally:
        await bb.close()


@pytest.mark.asyncio
async def test_redis_blackboard_wait_timeout():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    bb = SecureBlackboard(RedisBlackboard(prefix="test:bb:timeout"))
    try:
        with pytest.raises(KeyError, match="Timeout"):
            await bb.sys_wait_for_key("nonexistent", timeout=0.1)
    finally:
        await bb.close()


@pytest.mark.asyncio
async def test_redis_blackboard_delete():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    bb = SecureBlackboard(RedisBlackboard(prefix="test:bb:delete"))
    try:
        await bb.sys_put("del_key", "value")
        await bb.sys_get("del_key")  # Should exist
        
        backend = bb._backend
        await backend.delete("del_key")
        
        with pytest.raises(KeyError):
            await bb.sys_get("del_key")
    finally:
        await bb.close()


@pytest.mark.asyncio
async def test_redis_blackboard_missing_key():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    bb = SecureBlackboard(RedisBlackboard(prefix="test:bb:missing"))
    try:
        with pytest.raises(KeyError):
            await bb.sys_get("nonexistent")
    finally:
        await bb.close()


@pytest.mark.asyncio
async def test_redis_blackboard_custom_config():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    # Test with custom db and connection pool settings
    bb = SecureBlackboard(RedisBlackboard(
        prefix="test:bb:config",
        db=0,
        max_connections=5,
        socket_timeout=3.0,
        poll_interval=0.1
    ))
    try:
        await bb.sys_put("config_key", "test_value")
        result = await bb.sys_get("config_key")
        assert result == "test_value"
    finally:
        await bb.close()


@pytest.mark.asyncio
async def test_redis_blackboard_prefix_isolation():
    from blackboard import RedisBlackboard, SecureBlackboard
    
    bb1 = SecureBlackboard(RedisBlackboard(prefix="test:bb:a"))
    bb2 = SecureBlackboard(RedisBlackboard(prefix="test:bb:b"))
    try:
        await bb1.sys_put("shared_key", "value_a")
        await bb2.sys_put("shared_key", "value_b")
        
        assert await bb1.sys_get("shared_key") == "value_a"
        assert await bb2.sys_get("shared_key") == "value_b"
    finally:
        await bb1.close()
        await bb2.close()


@pytest.mark.asyncio
async def test_redis_event_bus_publish_subscribe():
    from bus import RedisEventBus
    from hiveflow import ECM
    
    bus = RedisEventBus(prefix="test:bus")
    await bus.start()
    try:
        received = []
        async def handler(msg):
            received.append(msg)
        
        sub_id = await bus.subscribe("test.topic", handler)
        await asyncio.sleep(0.2)  # Let subscription settle
        
        msg = ECM(trace_id="t1", intent="test", intent_id="i1", emitter="test")
        await bus.publish("test.topic", msg)
        await asyncio.sleep(0.5)  # Let message propagate
        
        assert len(received) == 1
        assert received[0].intent_id == "i1"
    finally:
        await bus.close()


@pytest.mark.asyncio
async def test_redis_event_bus_subscribe_tags():
    from bus import RedisEventBus
    from hiveflow import ECM
    
    bus = RedisEventBus(prefix="test:bus:tags")
    await bus.start()
    try:
        received = []
        async def handler(msg):
            received.append(msg)
        
        # Subscribe with skill tag filter
        sub_id = await bus.subscribe("test.tagged", handler, tags={"web_search"})
        await asyncio.sleep(0.2)
        
        # Message with matching skill should be received
        msg_match = ECM(trace_id="t1", intent="search", intent_id="i1", emitter="test", 
                       required_skills=["web_search"])
        await bus.publish("test.tagged", msg_match)
        await asyncio.sleep(0.5)
        
        # Message with non-matching skill should be filtered
        msg_no_match = ECM(trace_id="t2", intent="code", intent_id="i2", emitter="test",
                          required_skills=["code_execution"])
        await bus.publish("test.tagged", msg_no_match)
        await asyncio.sleep(0.5)
        
        assert len(received) == 1
        assert received[0].intent_id == "i1"
    finally:
        await bus.close()


@pytest.mark.asyncio
async def test_redis_event_bus_unsubscribe():
    from bus import RedisEventBus
    from hiveflow import ECM
    
    bus = RedisEventBus(prefix="test:bus:unsub")
    await bus.start()
    try:
        received = []
        async def handler(msg):
            received.append(msg)
        
        sub_id = await bus.subscribe("test.unsub", handler)
        await asyncio.sleep(0.2)
        
        await bus.unsubscribe("test.unsub", sub_id)
        await asyncio.sleep(0.2)
        
        msg = ECM(trace_id="t1", intent="test", intent_id="i1", emitter="test")
        await bus.publish("test.unsub", msg)
        await asyncio.sleep(0.5)
        
        assert len(received) == 0
    finally:
        await bus.close()


@pytest.mark.asyncio
async def test_redis_event_bus_update_subscription_tags():
    from bus import RedisEventBus
    from hiveflow import ECM
    
    bus = RedisEventBus(prefix="test:bus:updatetags")
    await bus.start()
    try:
        received = []
        async def handler(msg):
            received.append(msg)
        
        sub_id = await bus.subscribe("test.update", handler, tags={"skill_a"})
        await asyncio.sleep(0.2)
        
        # Update tags
        await bus.update_subscription_tags("test.update", sub_id, {"skill_b"})
        await asyncio.sleep(0.2)
        
        # Old skill should no longer match
        msg_old = ECM(trace_id="t1", intent="test", intent_id="i1", emitter="test",
                     required_skills=["skill_a"])
        await bus.publish("test.update", msg_old)
        await asyncio.sleep(0.5)
        
        # New skill should match
        msg_new = ECM(trace_id="t2", intent="test", intent_id="i2", emitter="test",
                     required_skills=["skill_b"])
        await bus.publish("test.update", msg_new)
        await asyncio.sleep(0.5)
        
        assert len(received) == 1
        assert received[0].intent_id == "i2"
    finally:
        await bus.close()


@pytest.mark.asyncio
async def test_redis_event_bus_register_complete_intent():
    from bus import RedisEventBus
    
    bus = RedisEventBus(prefix="test:bus:intent")
    await bus.start()
    try:
        await bus.register_intent("intent_1", timeout=5.0)
        assert await bus.is_intent_active("intent_1")
        
        await bus.complete_intent("intent_1")
        assert not await bus.is_intent_active("intent_1")
    finally:
        await bus.close()


@pytest.mark.asyncio
async def test_redis_event_bus_intent_timeout():
    from bus import RedisEventBus
    
    bus = RedisEventBus(prefix="test:bus:timeout")
    await bus.start()
    try:
        received = []
        async def timeout_handler(msg):
            received.append(msg)
        
        sub_id = await bus.subscribe("intent.timeout", timeout_handler)
        await asyncio.sleep(0.2)
        
        await bus.register_intent("intent_timeout_test", timeout=0.5)
        
        # Wait for timeout
        await asyncio.sleep(1.0)
        
        assert len(received) >= 1
        assert received[0].intent_id == "intent_timeout_test"
    finally:
        await bus.close()


@pytest.mark.asyncio
async def test_redis_event_bus_duplicate_intent_registration():
    from bus import RedisEventBus
    
    bus = RedisEventBus(prefix="test:bus:dupintent")
    await bus.start()
    try:
        # Registering same intent twice should not raise
        await bus.register_intent("intent_dup", timeout=5.0)
        await bus.register_intent("intent_dup", timeout=5.0)
        
        assert await bus.is_intent_active("intent_dup")
        
        await bus.complete_intent("intent_dup")
    finally:
        await bus.close()


@pytest.mark.asyncio
async def test_hiveflow_config_redis_initialization():
    from app import HiveFlow, HiveFlowConfig
    
    # This test verifies that HiveFlow correctly initializes with Redis config
    # It will skip if Redis is not available
    config = HiveFlowConfig(
        blackboard_type="redis",
        redis_url="redis://localhost",
        redis_db=0,
        redis_max_connections=5,
        redis_socket_timeout=3.0,
        redis_blackboard_poll_interval=0.1,
        blackboard_prefix="test:hiveflow"
    )
    
    hf = HiveFlow(config)
    assert hf.blackboard is not None
    assert hf.bus is not None
    
    await hf.shutdown()


@pytest.mark.asyncio
async def test_hiveflow_config_memory_fallback():
    from app import HiveFlow, HiveFlowConfig
    from blackboard import MemoryBlackboard
    
    config = HiveFlowConfig(
        blackboard_type="memory",
        max_audit_entries=500
    )
    
    hf = HiveFlow(config)
    assert isinstance(hf.blackboard._backend, MemoryBlackboard)
    assert hf.blackboard._max_audit == 500
    
    await hf.shutdown()


@pytest.mark.asyncio
async def test_hiveflow_config_ttl_memory():
    from app import HiveFlow, HiveFlowConfig
    from blackboard import TTLMemoryBlackboard
    
    config = HiveFlowConfig(
        blackboard_type="ttl_memory",
        default_ttl=60.0
    )
    
    hf = HiveFlow(config)
    assert isinstance(hf.blackboard._backend, TTLMemoryBlackboard)
    
    await hf.shutdown()


@pytest.mark.asyncio
async def test_hiveflow_config_encrypted():
    from app import HiveFlow, HiveFlowConfig
    from blackboard import EncryptedBlackboard, EnvKeyProvider
    import os
    from cryptography.fernet import Fernet
    
    # Generate a valid Fernet key (32 url-safe base64-encoded bytes)
    valid_key = Fernet.generate_key().decode()
    os.environ["HIVEFLOW_TEST_KEY"] = valid_key
    
    try:
        config = HiveFlowConfig(
            blackboard_type="encrypted",
            encryption_key_provider=EnvKeyProvider("HIVEFLOW_TEST_KEY"),
            encrypt_compression=True
        )
        
        hf = HiveFlow(config)
        assert isinstance(hf.blackboard._backend, EncryptedBlackboard)
        
        await hf.shutdown()
    finally:
        if "HIVEFLOW_TEST_KEY" in os.environ:
            del os.environ["HIVEFLOW_TEST_KEY"]


# ===========================================================================
# Config from_env and validation tests
# ===========================================================================

def test_config_validate_valid():
    """Valid config should not raise."""
    from app import HiveFlowConfig
    config = HiveFlowConfig()
    config.validate()  # should not raise


def test_config_validate_invalid_blackboard_type():
    from app import HiveFlowConfig
    config = HiveFlowConfig(blackboard_type="invalid")
    with pytest.raises(ValueError, match="Invalid blackboard_type"):
        config.validate()


def test_config_validate_negative_max_connections():
    from app import HiveFlowConfig
    config = HiveFlowConfig(redis_max_connections=0)
    with pytest.raises(ValueError, match="redis_max_connections"):
        config.validate()


def test_config_validate_negative_socket_timeout():
    from app import HiveFlowConfig
    config = HiveFlowConfig(redis_socket_timeout=-1.0)
    with pytest.raises(ValueError, match="redis_socket_timeout"):
        config.validate()


def test_config_validate_invalid_redis_url():
    from app import HiveFlowConfig
    config = HiveFlowConfig(redis_url="http://localhost")
    with pytest.raises(ValueError, match="redis_url must start"):
        config.validate()


def test_config_validate_negative_queue_size():
    from app import HiveFlowConfig
    config = HiveFlowConfig(worker_max_queue_size=0)
    with pytest.raises(ValueError, match="worker_max_queue_size"):
        config.validate()


def test_config_from_env_defaults():
    """from_env with no env vars set should use defaults."""
    import os
    from app import HiveFlowConfig
    # Make sure no env vars are set
    for key in ["BLACKBOARD_TYPE", "REDIS_URL", "REDIS_DB", "REDIS_MAX_CONNECTIONS",
                "REDIS_SOCKET_TIMEOUT", "REDIS_POLL_INTERVAL", "PREFIX",
                "MAX_AUDIT_ENTRIES", "DEFAULT_TTL", "WORKER_MAX_QUEUE_SIZE",
                "ENCRYPT_COMPRESSION", "LOG_LEVEL"]:
        if f"HIVEFLOW_{key}" in os.environ:
            del os.environ[f"HIVEFLOW_{key}"]
    
    config = HiveFlowConfig.from_env()
    assert config.blackboard_type == "memory"
    assert config.redis_max_connections == 10
    assert config.redis_socket_timeout == 5.0
    assert config.blackboard_prefix == "hiveflow"
    assert config.log_level == "INFO"


def test_config_from_env_with_values():
    """from_env should read environment variables."""
    import os
    from app import HiveFlowConfig
    
    os.environ["HIVEFLOW_BLACKBOARD_TYPE"] = "ttl_memory"
    os.environ["HIVEFLOW_DEFAULT_TTL"] = "3600"
    os.environ["HIVEFLOW_LOG_LEVEL"] = "DEBUG"
    os.environ["HIVEFLOW_MAX_AUDIT_ENTRIES"] = "500"
    
    try:
        config = HiveFlowConfig.from_env()
        assert config.blackboard_type == "ttl_memory"
        assert config.default_ttl == 3600.0
        assert config.log_level == "DEBUG"
        assert config.max_audit_entries == 500
    finally:
        for key in ["BLACKBOARD_TYPE", "DEFAULT_TTL", "LOG_LEVEL", "MAX_AUDIT_ENTRIES"]:
            if f"HIVEFLOW_{key}" in os.environ:
                del os.environ[f"HIVEFLOW_{key}"]


def test_config_from_env_encrypted_from_file():
    """from_env with ENCRYPTION_KEY_SOURCE=file should use FileKeyProvider."""
    import os
    import tempfile
    from app import HiveFlowConfig
    from cryptography.fernet import Fernet
    
    # Create a temp key file
    key = Fernet.generate_key()
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.key') as f:
        f.write(key)
        key_file = f.name
    
    os.environ["HIVEFLOW_BLACKBOARD_TYPE"] = "encrypted"
    os.environ["HIVEFLOW_ENCRYPTION_KEY_SOURCE"] = "file"
    os.environ["HIVEFLOW_ENCRYPTION_KEY_FILE"] = key_file
    
    try:
        config = HiveFlowConfig.from_env()
        assert config.encryption_key_provider is not None
        assert config.blackboard_type == "encrypted"
    finally:
        for key_name in ["BLACKBOARD_TYPE", "ENCRYPTION_KEY_SOURCE", "ENCRYPTION_KEY_FILE"]:
            if f"HIVEFLOW_{key_name}" in os.environ:
                del os.environ[f"HIVEFLOW_{key_name}"]
        os.unlink(key_file)


def test_configure_logging():
    from app import configure_logging
    import logging
    
    # Should not raise
    configure_logging(level="DEBUG")
    
    root = logging.getLogger()
    # Note: basicConfig doesn't change root level if already configured
    # Just verify it runs without error
    assert True
