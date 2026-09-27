"""Pytest configuration for HiveFlow Core tests.

This conftest provides fixtures for:
- Event loop setup (pytest-asyncio)
- Blackboard backends (Memory, TTL, Secure)
- Scheduler with mock components
- Orchestrator with mock blackboard
- Guards with mock LLM client

All tests are isolated and don't depend on external services.
"""
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure packages/core is on path
_core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

from hiveflow import (
    Capability,
    ECM,
    Expectation,
    HiveFlowConfig,
    InputGuard,
    MemoryBlackboard,
    SecureBlackboard,
    TTLMemoryBlackboard,
)
from hiveflow.blackboard import AuditedBlackboardView, BlackboardBackend
from hiveflow.bus import EventBus, InProcessEventBus
from hiveflow.scheduler import InProcessScheduler, SchedulerConfig
from hiveflow.orchestrator import DAGOrchestrator, DynamicOrchestrator


# ========== Event Loop Fixture ==========

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ========== Configuration Fixture ==========

@pytest.fixture
def hiveflow_config():
    """Basic HiveFlow configuration for tests."""
    return HiveFlowConfig(
        blackboard_type="memory",
        worker_max_queue_size=100,
        auction_agent_threshold=20,
    )


# ========== Blackboard Fixtures ==========

@pytest.fixture
async def memory_blackboard():
    """Memory blackboard instance."""
    bb = MemoryBlackboard()
    yield bb
    await bb.close()


@pytest.fixture
async def ttl_blackboard():
    """TTL memory blackboard with cleanup loop."""
    bb = TTLMemoryBlackboard(cleanup_interval=10.0)
    await bb.start()
    yield bb
    await bb.shutdown()


@pytest.fixture
async def secure_blackboard(memory_blackboard):
    """Secure blackboard with audit logging."""
    return SecureBlackboard(memory_blackboard)


@pytest.fixture
def audited_view(secure_blackboard):
    """Audited blackboard view for a test agent."""
    cap = Capability(
        agent_id="test_agent",
        skills={"test"},
        read_keys={"test:*", "public:*"},
        write_keys={"test:*"},
    )
    return AuditedBlackboardView(secure_blackboard, cap)


# ========== Bus Fixtures ==========

@pytest.fixture
async def inprocess_bus():
    """In-process event bus."""
    bus = InProcessEventBus()
    await bus.start()
    yield bus
    await bus.close()


@pytest.fixture
def mock_redis_bus():
    """Mock Redis event bus (doesn't connect to real Redis)."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock(return_value=None)
    bus.subscribe = AsyncMock(return_value=None)
    bus.register_intent = AsyncMock(return_value=None)
    bus.complete_intent = AsyncMock(return_value=None)
    return bus


# ========== Scheduler Fixtures ==========

@pytest.fixture
async def scheduler(inprocess_bus):
    """In-process scheduler with memory bus."""
    config = SchedulerConfig(selection_strategy="least_loaded")
    sched = InProcessScheduler(bus=inprocess_bus, config=config)
    await sched.start()
    yield sched
    await sched.close()


@pytest.fixture
def mock_worker():
    """Mock worker with assignable task queue."""
    class MockWorker:
        def __init__(self, agent_id: str):
            self.agent_id = agent_id
            self.queue = asyncio.Queue()
            self.tasks_received = []
        
        async def assign_task(self, ecm: ECM):
            self.tasks_received.append(ecm)
            await self.queue.put(ecm)
    
    return MockWorker


@pytest.fixture
def mock_capability():
    """Create mock capability for testing."""
    def _create(agent_id: str, skills: set[str], load: float = 0.0):
        return Capability(
            agent_id=agent_id,
            skills=skills,
            read_keys={"test:*"},
            write_keys={"test:*"},
            load=load,
        )
    return _create


@pytest.fixture
def ecm_factory():
    """Factory for creating ECM messages."""
    def _create(intent: str, skills: list[str], trace_id: str = "test-trace"):
        return ECM(
            trace_id=trace_id,
            intent=intent,
            intent_id=f"intent-{intent}",
            emitter="test",
            required_skills=skills,
        )
    return _create


# ========== Orchestrator Fixtures ==========

@pytest.fixture
async def dag_orchestrator(memory_blackboard):
    """DAG orchestrator with memory blackboard."""
    secure_bb = SecureBlackboard(memory_blackboard)
    orch = DAGOrchestrator(blackboard=secure_bb)
    yield orch


@pytest.fixture
async def dynamic_orchestrator(memory_blackboard):
    """Dynamic orchestrator with memory blackboard."""
    secure_bb = SecureBlackboard(memory_blackboard)
    orch = DynamicOrchestrator(blackboard=secure_bb)
    yield orch


@pytest.fixture
def simple_task():
    """Simple async task for testing."""
    async def _task(deps: dict, view: AuditedBlackboardView) -> Any:
        return {"result": "success"}
    return _task


@pytest.fixture
def failing_task():
    """Task that raises an exception."""
    async def _task(deps: dict, view: AuditedBlackboardView) -> Any:
        raise ValueError("Task failed intentionally")
    return _task


@pytest.fixture
def retry_task():
    """Task that fails first N times, then succeeds."""
    def _create(fail_count: int = 2):
        counter = 0
        async def _task(deps: dict, view: AuditedBlackboardView) -> Any:
            nonlocal counter
            counter += 1
            if counter <= fail_count:
                raise RuntimeError(f"Attempt {counter} failed")
            return {"result": "success", "attempts": counter}
        return _task
    return _create


# ========== Guard Fixtures ==========

@pytest.fixture
def input_guard():
    """Basic input guard."""
    return InputGuard(max_length=10000)


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for guard testing."""
    client = MagicMock()
    response = MagicMock()
    response.content = "SAFE - No issues detected"
    client.chat = AsyncMock(return_value=response)
    return client


@pytest.fixture
def mock_llm_blocking():
    """Mock LLM client that blocks content."""
    client = MagicMock()
    response = MagicMock()
    response.content = "BLOCKED - Contains malicious content"
    client.chat = AsyncMock(return_value=response)
    return client


# ========== Helper Functions ==========

@pytest.fixture
def create_graph():
    """Factory for creating test graphs."""
    def _create(nodes: dict[str, dict]) -> dict:
        """
        Create a graph for orchestrator testing.
        
        Args:
            nodes: Dict of node_name -> {task, depends_on, retry, timeout, etc.}
        
        Returns:
            Graph dict suitable for orchestrator.execute()
        """
        graph = {}
        for name, config in nodes.items():
            graph[name] = {
                "task": config.get("task"),
                "depends_on": config.get("depends_on", []),
            }
            if "retry" in config:
                graph[name]["retry"] = config["retry"]
            if "timeout" in config:
                graph[name]["timeout"] = config["timeout"]
        return graph
    return _create


# ========== Time Control ==========

@pytest.fixture
def time_mock(monkeypatch):
    """Mock time.monotonic for testing timeouts."""
    current_time = 0.0
    
    def _time():
        return current_time
    
    def _advance(seconds: float):
        nonlocal current_time
        current_time += seconds
    
    monkeypatch.setattr("time.monotonic", _time)
    
    return {"time": _time, "advance": _advance}