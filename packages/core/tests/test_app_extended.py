"""
Extended tests for app module (HiveFlow and HiveFlowConfig) to improve coverage.
Target: Increase app.py coverage from 30% to 70%.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from hiveflow import ECM, HiveFlow, HiveFlowConfig


class TestHiveFlowConfigValidation:
    """Test HiveFlowConfig validation."""

    def test_valid_config_defaults(self):
        """Test config with default values."""
        config = HiveFlowConfig()
        assert config.blackboard_type == "memory"
        assert config.redis_db == 0
        assert config.max_audit_entries == 1000
        assert config.worker_max_queue_size == 100
        assert config.log_level == "INFO"

    def test_valid_config_custom_values(self):
        """Test config with custom values."""
        config = HiveFlowConfig(
            blackboard_type="ttl_memory",
            redis_url="redis://localhost:6379",
            redis_db=1,
            redis_max_connections=20,
            redis_socket_timeout=10.0,
            max_audit_entries=500,
            worker_max_queue_size=50,
            log_level="DEBUG",
            use_json_schema=True,
            default_ttl=60.0,
        )

        assert config.blackboard_type == "ttl_memory"
        assert config.redis_db == 1
        assert config.redis_max_connections == 20
        assert config.max_audit_entries == 500

    def test_validate_invalid_blackboard_type(self):
        """Test validation rejects invalid blackboard type."""
        config = HiveFlowConfig(blackboard_type="invalid_type")

        with pytest.raises(ValueError, match="Invalid blackboard_type"):
            config.validate()

    def test_validate_negative_redis_max_connections(self):
        """Test validation rejects negative redis_max_connections."""
        config = HiveFlowConfig(redis_max_connections=-1)

        with pytest.raises(ValueError, match="redis_max_connections must be >= 1"):
            config.validate()

    def test_validate_zero_redis_socket_timeout(self):
        """Test validation rejects zero socket timeout."""
        config = HiveFlowConfig(redis_socket_timeout=0)

        with pytest.raises(ValueError, match="redis_socket_timeout must be > 0"):
            config.validate()

    def test_validate_negative_poll_interval(self):
        """Test validation rejects negative poll interval."""
        config = HiveFlowConfig(redis_blackboard_poll_interval=-0.1)

        with pytest.raises(ValueError, match="redis_blackboard_poll_interval must be > 0"):
            config.validate()

    def test_validate_negative_max_audit_entries(self):
        """Test validation rejects negative max_audit_entries."""
        config = HiveFlowConfig(max_audit_entries=-1)

        with pytest.raises(ValueError, match="max_audit_entries must be >= 0"):
            config.validate()

    def test_validate_small_worker_queue_size(self):
        """Test validation rejects worker queue size < 1."""
        config = HiveFlowConfig(worker_max_queue_size=0)

        with pytest.raises(ValueError, match="worker_max_queue_size must be >= 1"):
            config.validate()

    def test_validate_invalid_redis_url(self):
        """Test validation rejects invalid Redis URL format."""
        config = HiveFlowConfig(redis_url="http://invalid")

        with pytest.raises(ValueError, match="redis_url must start with redis://"):
            config.validate()

    def test_validate_valid_redis_url(self):
        """Test validation accepts valid Redis URLs."""
        config1 = HiveFlowConfig(redis_url="redis://localhost:6379")
        config1.validate()  # Should not raise

        config2 = HiveFlowConfig(redis_url="rediss://secure-redis:6380")
        config2.validate()  # Should not raise


class TestHiveFlowConfigFromEnv:
    """Test HiveFlowConfig.from_env()."""

    def test_from_env_defaults(self, monkeypatch):
        """Test from_env with no environment variables."""
        # Clear all HIVEFLOW_ env vars
        import os
        for key in list(os.environ.keys()):
            if key.startswith("HIVEFLOW"):
                monkeypatch.delenv(key, raising=False)

        config = HiveFlowConfig.from_env()
        assert config.blackboard_type == "memory"

    def test_from_env_with_custom_values(self, monkeypatch):
        """Test from_env with custom environment variables."""
        monkeypatch.setenv("HIVEFLOW_BLACKBOARD_TYPE", "ttl_memory")
        monkeypatch.setenv("HIVEFLOW_REDIS_URL", "redis://custom:6379")
        monkeypatch.setenv("HIVEFLOW_REDIS_DB", "2")
        monkeypatch.setenv("HIVEFLOW_MAX_AUDIT_ENTRIES", "2000")
        monkeypatch.setenv("HIVEFLOW_LOG_LEVEL", "WARNING")

        config = HiveFlowConfig.from_env()

        assert config.blackboard_type == "ttl_memory"
        assert config.redis_url == "redis://custom:6379"
        assert config.redis_db == 2
        assert config.max_audit_entries == 2000
        assert config.log_level == "WARNING"

    def test_from_env_custom_prefix(self, monkeypatch):
        """Test from_env with custom prefix."""
        monkeypatch.setenv("CUSTOM_BLACKBOARD_TYPE", "encrypted")

        config = HiveFlowConfig.from_env(prefix="CUSTOM")
        assert config.blackboard_type == "encrypted"


@pytest.mark.asyncio
class TestHiveFlowLifecycle:
    """Test HiveFlow engine lifecycle."""

    async def test_hiveflow_start_shutdown(self):
        """Test basic start and shutdown."""
        config = HiveFlowConfig()
        hf = HiveFlow(config)

        await hf.start()
        assert hf.bus is not None
        assert hf.scheduler is not None
        assert hf.blackboard is not None

        await hf.shutdown()

    async def test_hiveflow_with_ttl_memory_blackboard(self):
        """Test HiveFlow with TTL memory blackboard."""
        config = HiveFlowConfig(
            blackboard_type="ttl_memory",
            default_ttl=30.0
        )
        hf = HiveFlow(config)

        await hf.start()
        await hf.blackboard.sys_put("test_key", "test_value")

        value = await hf.blackboard.sys_get("test_key")
        assert value == "test_value"

        await hf.shutdown()

    async def test_hiveflow_register_agent_handler(self):
        """Test registering agent handler."""
        config = HiveFlowConfig()
        hf = HiveFlow(config)

        async def my_handler(ecm, view):
            return {"handled": True}

        hf.register_agent_handler("test-agent", my_handler)
        assert "test-agent" in hf._handler_registry

    async def test_hiveflow_create_agent(self):
        """Test creating an agent."""
        config = HiveFlowConfig()
        hf = HiveFlow(config)
        await hf.start()

        async def handler(ecm, view):
            return {"status": "ok"}

        worker = await hf.create_agent(
            agent_id="test-agent",
            skills={"test_skill"},
            read_keys=set(),
            write_keys=set(),
            task_handler=handler,
        )

        assert worker is not None
        assert worker.agent_id == "test-agent"

        await hf.shutdown()

    async def test_hiveflow_save_and_restore_state(self):
        """Test state save and restore preserves agent skills."""
        import json

        config = HiveFlowConfig()
        hf = HiveFlow(config)
        await hf.start()

        async def handler(ecm, view):
            return {}

        await hf.create_agent(
            agent_id="stateful-agent",
            skills={"skill1", "skill2"},
            read_keys={"input"},
            write_keys={"output"},
            task_handler=handler,
        )

        await hf.save_state()
        state_data = await hf.blackboard.sys_get("__hiveflow_state__:agents")
        assert state_data is not None

        parsed = json.loads(state_data)
        assert parsed["version"] == 3
        cap = parsed["caps"][0]
        assert set(cap["skills"]) == {"skill1", "skill2"}
        assert set(cap["read_keys"]) == {"input"}
        assert set(cap["write_keys"]) == {"output"}

        await hf.cell.stop_worker("stateful-agent")
        hf.register_agent_handler("stateful-agent", handler)
        await hf.restore_state()

        restored = hf.scheduler._capabilities.get("stateful-agent")
        assert restored is not None
        assert restored.skills == {"skill1", "skill2"}
        assert restored.read_keys == {"input"}
        assert restored.write_keys == {"output"}

        await hf.shutdown()

    async def test_hiveflow_set_strategy(self):
        """Test setting custom scheduling strategy."""
        config = HiveFlowConfig()
        hf = HiveFlow(config)
        await hf.start()

        mock_strategy = MagicMock()
        mock_strategy.start = AsyncMock()
        mock_strategy.stop = AsyncMock()
        await hf.set_strategy(mock_strategy)
        assert hf._custom_strategy is mock_strategy
        assert hf.scheduler.strategy is mock_strategy

        await hf.shutdown()


@pytest.mark.asyncio
class TestHiveFlowAgentWorkflow:
    """Test complete agent workflows."""

    async def test_single_agent_workflow(self):
        """Test simple single agent workflow."""
        config = HiveFlowConfig()
        hf = HiveFlow(config)
        await hf.start()

        execution_log = []

        async def simple_handler(ecm, view):
            execution_log.append({
                "intent": ecm.intent,
                "emitter": ecm.emitter,
            })
            await view.put("result", {"completed": True})
            return {"status": "done"}

        await hf.create_agent(
            agent_id="simple-agent",
            skills={"execute"},
            read_keys=set(),
            write_keys={"result"},
            task_handler=simple_handler,
        )

        # Schedule task
        ecm = ECM(
            trace_id="workflow-1",
            intent="Execute simple task",
            intent_id="exec-1",
            emitter="user",
            required_skills=["execute"],
            payload={},
        )

        await hf.scheduler.schedule(ecm)
        await asyncio.sleep(0.3)

        assert len(execution_log) == 1
        assert execution_log[0]["emitter"] == "user"

        result = await hf.blackboard.sys_get("result")
        assert result["completed"] is True

        await hf.shutdown()

    async def test_multi_agent_sequential_workflow(self):
        """Test sequential multi-agent workflow."""
        config = HiveFlowConfig()
        hf = HiveFlow(config)
        await hf.start()

        async def producer_handler(ecm, view):
            await view.put("produced_data", {"value": 100})
            return {"produced": True}

        async def consumer_handler(ecm, view):
            data = await view.get("produced_data")
            processed = {"value": data["value"] * 2}
            await view.put("consumed_data", processed)
            return {"consumed": True}

        await hf.create_agent(
            agent_id="producer",
            skills={"produce"},
            read_keys=set(),
            write_keys={"produced_data"},
            task_handler=producer_handler,
        )

        await hf.create_agent(
            agent_id="consumer",
            skills={"consume"},
            read_keys={"produced_data"},
            write_keys={"consumed_data"},
            task_handler=consumer_handler,
        )

        # Schedule producer
        ecm1 = ECM(
            trace_id="workflow-2",
            intent="Produce data",
            intent_id="produce-1",
            emitter="system",
            required_skills=["produce"],
            payload={},
        )
        await hf.scheduler.schedule(ecm1)
        await asyncio.sleep(0.2)

        # Schedule consumer
        ecm2 = ECM(
            trace_id="workflow-2",
            intent="Consume data",
            intent_id="consume-1",
            emitter="system",
            required_skills=["consume"],
            payload={},
        )
        await hf.scheduler.schedule(ecm2)
        await asyncio.sleep(0.2)

        consumed = await hf.blackboard.sys_get("consumed_data")
        assert consumed["value"] == 200

        await hf.shutdown()

    async def test_agent_with_read_write_permissions(self):
        """Test agent respecting read/write permissions."""
        config = HiveFlowConfig()
        hf = HiveFlow(config)
        await hf.start()

        async def restricted_handler(ecm, view):
            # This agent can only read from allowed keys
            try:
                await view.get("forbidden_key")
                return {"error": "should_not_reach"}
            except PermissionError:
                return {"permission_denied": True}

        await hf.create_agent(
            agent_id="restricted-agent",
            skills={"restricted"},
            read_keys={"allowed_key"},  # Only this key
            write_keys={"result"},
            task_handler=restricted_handler,
        )

        ecm = ECM(
            trace_id="workflow-3",
            intent="Test permissions",
            intent_id="perm-1",
            emitter="test",
            required_skills=["restricted"],
            payload={},
        )

        await hf.scheduler.schedule(ecm)
        await asyncio.sleep(0.3)

        await hf.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=hiveflow.app", "--cov-report=term-missing"])
