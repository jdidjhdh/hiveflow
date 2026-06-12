"""Agent load history and recent task tracking tests."""
import os

import pytest
import pytest_asyncio

os.environ.setdefault("HIVEFLOW_AGENT_ECHO_LLM", "true")


@pytest_asyncio.fixture
async def engine():
    from app.core.engine_service import EngineService
    svc = EngineService()
    await svc.start()
    yield svc
    await svc.shutdown()


@pytest.mark.asyncio
async def test_agent_load_history_and_recent_tasks(engine):
    engine.record_node_execution("node-a", 100.0, "intent-1")
    perf = engine.get_agent_performance()
    assert isinstance(perf, list)

    engine._record_agent_task("studio-summarize", "intent-1", "completed", {"duration_ms": 250})
    agents = await engine.list_agents()
    assert isinstance(agents, list)

    if agents:
        agent = agents[0]
        assert "load_history" in agent
        assert "recent_tasks" in agent
        assert isinstance(agent["load_history"], list)
        assert isinstance(agent["recent_tasks"], list)

    settings = engine.get_scheduler_settings()
    assert settings["strategy"] in ("least_loaded", "auction")
    await engine.set_scheduler_settings("auction", 6)
    assert engine.get_scheduler_settings()["strategy"] == "auction"
    await engine.set_scheduler_settings("least_loaded", 5)
