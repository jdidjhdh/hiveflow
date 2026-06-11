"""Analytics API endpoint tests."""
import os
from unittest.mock import AsyncMock, patch

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
async def test_node_duration_stats(engine):
    engine.record_node_execution("summarize", 120.0, "i1")
    engine.record_node_execution("summarize", 80.0, "i2")
    stats = engine.get_node_duration_stats()
    assert isinstance(stats, list)
    assert any(s["node_name"] == "summarize" for s in stats)
    assert stats[0]["call_count"] >= 2


@pytest.mark.asyncio
async def test_workflow_trend_buckets(engine):
    engine.record_intent("i1", "test", "studio", "completed")
    trend = engine.get_workflow_trend(days=7)
    assert len(trend) == 7
    assert "date" in trend[0]
    assert "executions" in trend[0]


class TestAnalyticsHTTP:
    def test_nodes_duration_endpoint(self, client, initialized_engine):
        resp = client.get("/api/analytics/nodes/duration")
        assert resp.status_code == 200
        assert "nodes" in resp.json()

    def test_workflow_trend_endpoint(self, client, initialized_engine):
        resp = client.get("/api/analytics/workflows/trend?days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert "trend" in data
        assert data["period_days"] == 7

    def test_plan_only_endpoint(self, client, initialized_engine):
        client.post("/api/agent/runtime", json={"mode": "agent"})
        resp = client.post("/api/agent/plan-only", json={"query": "summarize docs"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "planned"
        assert "plan" in data
        assert "final_answer" in data["plan"]

    def test_execute_plan_endpoint(self, client, initialized_engine):
        from app.core.engine_service import get_engine

        client.post("/api/agent/runtime", json={"mode": "agent"})
        plan = {"final_answer": {"task": "summarize", "depends_on": []}}
        engine = get_engine()
        with patch.object(
            engine,
            "run_agent_execute_plan",
            new=AsyncMock(return_value={
                "answer": "mock plan result",
                "intent_id": "exec-plan-intent",
                "status": "completed",
                "raw_results": {"final_answer": "mock plan result"},
            }),
        ):
            resp = client.post(
                "/api/agent/execute-plan",
                json={"plan": plan, "query": "execute test plan"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "completed"
        assert "answer" in data

    def test_prometheus_analytics_endpoint(self, client, initialized_engine):
        resp = client.get("/api/analytics/prometheus")
        assert resp.status_code == 200
        body = resp.json()
        assert "metrics" in body
        assert "nodes" in body

    def test_plan_only_503_in_core_mode(self, client, initialized_engine):
        client.post("/api/agent/runtime", json={"mode": "core"})
        resp = client.post("/api/agent/plan-only", json={"query": "fail"})
        assert resp.status_code == 503
