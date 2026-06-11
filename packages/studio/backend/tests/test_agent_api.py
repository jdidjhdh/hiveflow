"""Studio Agent mode, Replay API, and MCP auto-register integration tests."""
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.engine_service import EngineService

# 测试环境使用 Echo LLM，避免连接 Ollama/OpenAI
os.environ.setdefault("HIVEFLOW_AGENT_ECHO_LLM", "true")


@pytest_asyncio.fixture
async def engine():
    svc = EngineService()
    await svc.start()
    yield svc
    await svc.shutdown()


@pytest.mark.asyncio
async def test_runtime_default_is_core(engine):
    info = engine.get_runtime_info()
    assert info["runtime_mode"] == "core"
    assert info["agent_active"] is False


@pytest.mark.asyncio
async def test_switch_to_agent_mode(engine):
    info = await engine.set_runtime_mode("agent")
    assert info["runtime_mode"] == "agent"
    assert info["agent_active"] is True
    assert "general" in info["skills"] or "summarize" in info["skills"]

    back = await engine.set_runtime_mode("core")
    assert back["runtime_mode"] == "core"
    assert back["agent_active"] is False


@pytest.mark.asyncio
async def test_agent_query_in_agent_mode(engine):
    await engine.set_runtime_mode("agent")
    result = await engine.run_agent_query("hello from studio test")
    assert "answer" in result
    assert result.get("intent_id")


@pytest.mark.asyncio
async def test_agent_query_fails_in_core_mode(engine):
    with pytest.raises(RuntimeError, match="Agent runtime is not active"):
        await engine.run_agent_query("should fail")


@pytest.mark.asyncio
async def test_plan_hitl_shared_manager(engine):
    """Agent runtime shares Studio HITLManager when plan HITL is enabled."""
    os.environ["HIVEFLOW_PLAN_HITL"] = "true"
    try:
        await engine.set_runtime_mode("agent")
        studio_mgr = engine.get_hitl_manager()
        agent_mgr = engine._hive_mind.config.hitl_manager
        assert studio_mgr is agent_mgr
    finally:
        os.environ.pop("HIVEFLOW_PLAN_HITL", None)
        await engine.set_runtime_mode("core")


@pytest.mark.asyncio
async def test_replay_debugger_reads_audit(engine):
    await engine.engine.blackboard.sys_put("replay:test", {"x": 1})
    dbg = engine.get_replay_debugger()
    events = dbg.get_audit_timeline(limit=20)
    assert isinstance(events, list)
    session = dbg.build_replay_session("intent-demo")
    assert session["intent_id"] == "intent-demo"


@pytest.mark.asyncio
async def test_mcp_auto_register_skills(engine):
    await engine.set_runtime_mode("agent")

    mock_tool = MagicMock()
    mock_tool.name = "search"
    mock_tool.description = "Search the web"

    pm = engine.get_plugin_manager()
    pm.initialize_plugin = AsyncMock()
    pm.get_plugin_tools = AsyncMock(return_value=[mock_tool])
    pm.call_tool = AsyncMock(
        return_value=MagicMock(success=True, content="ok", error=None)
    )

    skills = await engine.auto_register_mcp_skills("demo_plugin")
    assert "mcp_demo_plugin_search" in skills
    assert "mcp_demo_plugin_search" in engine._hive_mind.config.skill_registry


@pytest.mark.asyncio
async def test_mcp_auto_register_skipped_in_core_mode(engine):
    skills = await engine.auto_register_mcp_skills("any")
    assert skills == []


class TestAgentHTTPAPI:
    def test_get_runtime(self, client, initialized_engine):
        resp = client.get("/api/agent/runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runtime_mode"] in ("core", "agent")

    def test_set_runtime_agent(self, client, initialized_engine):
        resp = client.post("/api/agent/runtime", json={"mode": "agent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["runtime_mode"] == "agent"
        assert data["agent_active"] is True

    def test_agent_query_http(self, client, initialized_engine):
        client.post("/api/agent/runtime", json={"mode": "agent"})
        engine = get_engine()
        with patch.object(
            engine,
            "run_agent_query",
            new=AsyncMock(return_value={
                "answer": "mock answer",
                "intent_id": "test-intent",
                "status": "completed",
                "raw_results": {},
            }),
        ):
            resp = client.post(
                "/api/agent/query",
                json={"query": "ping from http test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "mock answer"

    def test_agent_query_503_in_core_mode(self, client, initialized_engine):
        client.post("/api/agent/runtime", json={"mode": "core"})
        resp = client.post("/api/agent/query", json={"query": "fail"})
        assert resp.status_code == 503

    def test_export_langgraph_http(self, client, initialized_engine):
        plan = {
            "research": {"task": "search", "depends_on": []},
            "final_answer": {"task": "summarize", "depends_on": ["research"]},
        }
        resp = client.post(
            "/api/agent/export-langgraph",
            json={"plan": plan, "workflow_id": "http_test", "include_python": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_count"] == 2
        assert data["spec"]["workflow_id"] == "http_test"
        assert "python" in data
        assert "StateGraph" in data["python"]

    def test_export_langgraph_empty_plan(self, client, initialized_engine):
        resp = client.post("/api/agent/export-langgraph", json={"plan": {}})
        assert resp.status_code == 400

    def test_replay_audit_http(self, client, initialized_engine):
        client.post("/api/blackboard/keys/replay-k", json={"value": {"a": 1}})
        resp = client.get("/api/replay/audit?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data

    def test_replay_audit_by_intent(self, client, initialized_engine):
        resp = client.get("/api/replay/audit?intent_id=test-intent&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == "test-intent"


class TestPluginMCPAutoRegister:
    def test_install_returns_registered_skills_in_agent_mode(self, client, initialized_engine):
        client.post("/api/agent/runtime", json={"mode": "agent"})

        mock_tool = MagicMock()
        mock_tool.name = "fetch"
        mock_tool.description = "Fetch URL"

        with patch("hiveflow.PluginMarketplace") as MockMarketplace:
            marketplace = MockMarketplace.return_value
            marketplace.install_plugin = AsyncMock(return_value=True)

            pm = get_engine().get_plugin_manager()
            pm.initialize_plugin = AsyncMock()
            pm.get_plugin_tools = AsyncMock(return_value=[mock_tool])
            pm.call_tool = AsyncMock(
                return_value=MagicMock(success=True, content="data", error=None)
            )

            resp = client.post(
                "/api/plugins/install",
                json={"plugin_id": "http_plugin", "config": {}},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "installed"
            assert "mcp_http_plugin_fetch" in body.get("registered_skills", [])


def get_engine():
    from app.core.engine_service import get_engine as _get
    return _get()
