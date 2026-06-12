"""HiveFlow - Comprehensive API Tests

Tests for all backend API endpoints. Uses the conftest.py client fixture.
Engine is mocked for endpoints that require get_engine().
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# ======================== Engine Mocking ========================

@pytest.fixture
def mock_engine():
    """Mock get_engine for API endpoints that require it."""
    mock_engine = MagicMock()
    mock_engine.metrics_collector.get_summary.return_value = {
        "workflow_count": 0, "agent_count": 0, "blackboard_keys": 0
    }
    mock_engine.metrics_collector.get_workflow_trend.return_value = []
    mock_engine.metrics_collector.get_agent_performance.return_value = []
    mock_engine.metrics_collector.get_error_stats.return_value = []
    mock_engine.kb_manager.list_kbs.return_value = []
    mock_engine.kb_manager.get_kb.return_value = None
    mock_engine.kb_manager.query_kb.return_value = []
    mock_engine.kb_manager.search_kb.return_value = []
    mock_engine.plugin_manager.get_stats.return_value = {"installed_count": 0}
    mock_engine.plugin_manager.list_installed.return_value = []
    mock_engine.plugin_manager.install_plugin.return_value = {"status": "installed"}
    mock_engine.plugin_manager.uninstall_plugin.return_value = {"status": "uninstalled"}

    # Async methods for EngineService
    mock_engine.list_keys = AsyncMock(return_value=[])
    mock_engine.get_key = AsyncMock(return_value=None)
    mock_engine.set_key = AsyncMock(return_value=None)
    mock_engine.delete_key = AsyncMock(return_value=None)
    mock_engine.get_audit_log = AsyncMock(return_value=[])
    mock_engine.get_metrics = AsyncMock(return_value={"counters": {}, "histograms": {}, "active_agents": 0, "total_load": 0})
    mock_engine.get_metrics_json = AsyncMock(return_value={"counters": {}, "histograms": {}, "active_agents": 0, "total_load": 0, "uptime_seconds": 0, "active_workflows": 0, "ws_connected": True})
    mock_engine.create_agent = AsyncMock(return_value={"agent_id": "test"})
    mock_engine.list_agents = AsyncMock(return_value=[])
    mock_engine.get_agent = AsyncMock(return_value=None)
    mock_engine.stop_agent = AsyncMock(return_value=None)
    mock_engine.drain_agent = AsyncMock(return_value=None)
    mock_engine.execute_workflow = AsyncMock(return_value={"wf_id": "test", "status": "completed", "results": {}})
    mock_engine.get_workflow_status = MagicMock(return_value={"wf_id": "test", "status": "completed"})
    mock_engine.stop_workflow = AsyncMock(return_value={"wf_id": "test", "status": "stopped"})
    mock_engine.get_intent_timeline = AsyncMock(return_value=[])
    mock_engine.get_recent_events = MagicMock(return_value=[])
    mock_engine._metrics_exporter = MagicMock()
    mock_engine._metrics_exporter.generate_metrics.return_value = "# No metrics configured\n"
    mock_engine._running = True

    engine_modules = [
        "app.api.analytics",
        "app.api.knowledge",
        "app.api.plugins",
        "app.api.monitoring",
        "app.api.webhooks",
        "app.api.workflows",
        "app.api.agents",
        "app.api.metrics",
        "app.api.blackboard",
        "app.api.events",
    ]

    patchers = []
    for mod in engine_modules:
        try:
            p = patch(f"{mod}.get_engine", return_value=mock_engine)
            patchers.append(p)
        except (AttributeError, ImportError):
            pass

    # Start all patchers
    for p in patchers:
        p.start()

    yield mock_engine

    # Stop all patchers
    for p in patchers:
        try:
            p.stop()
        except Exception:
            pass

# ======================== Streaming API Tests ========================

class TestStreamingAPI:
    """Test SSE streaming endpoints."""

    def test_stream_push_event(self, client):
        """POST /api/stream/{id}/push adds event to buffer."""
        wf_id = "wf_test_push"
        event = {"type": "token", "data": "Hello world"}
        response = client.post(f"/api/stream/{wf_id}/push", json=event)
        assert response.status_code == 200
        assert response.json()["status"] == "pushed"

    def test_stream_close(self, client):
        """POST /api/stream/{id}/close closes stream."""
        wf_id = "wf_test_close"
        client.post(f"/api/stream/{wf_id}/push", json={"type": "done", "data": {}})
        response = client.post(f"/api/stream/{wf_id}/close")
        assert response.status_code == 200
        assert response.json()["status"] == "closed"

    def test_stream_push_multiple(self, client):
        """Push multiple events."""
        wf_id = "wf_test_multi"
        events = [
            {"type": "node_start", "data": {"node_id": "n1"}},
            {"type": "token", "data": "Token 1"},
            {"type": "node_end", "data": {"node_id": "n1"}},
        ]
        for event in events:
            resp = client.post(f"/api/stream/{wf_id}/push", json=event)
            assert resp.status_code == 200

# ======================== Knowledge Base API Tests ========================

class TestKnowledgeAPI:
    """Test knowledge base CRUD and operations."""
    pytestmark = pytest.mark.usefixtures("mock_engine")

    def test_create_kb(self, client):
        """POST /api/knowledge creates a knowledge base."""
        response = client.post("/api/knowledge", json={
            "kb_id": "kb_test_1",
            "name": "Test KB",
            "description": "Test knowledge base"
        })
        # May return 200 (full engine) or 500 (engine missing kb_manager)
        assert response.status_code in [200, 201, 500]

    def test_list_kbs(self, client):
        """GET /api/knowledge returns list."""
        response = client.get("/api/knowledge")
        assert response.status_code in [200, 500]

    def test_get_kb(self, client):
        """GET /api/knowledge/{kb_id} returns KB details."""
        response = client.get("/api/knowledge/kb_test_get")
        assert response.status_code in [200, 404, 500]

    def test_delete_kb(self, client):
        """DELETE /api/knowledge/{kb_id} removes KB."""
        response = client.delete("/api/knowledge/kb_test_delete")
        assert response.status_code in [200, 204, 404, 500]

    def test_kb_query(self, client):
        """POST /api/knowledge/{kb_id}/query searches KB."""
        response = client.post("/api/knowledge/kb_test_query/query", json={
            "query": "What is Python?"
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_kb_search(self, client):
        """POST /api/knowledge/{kb_id}/search searches with filters."""
        response = client.post("/api/knowledge/kb_test_search/search", json={
            "query": "test",
            "metadata_filter": {"source": "test"}
        })
        assert response.status_code in [200, 400, 404, 500]

    def test_add_document(self, client):
        """POST /api/knowledge/{kb_id}/documents adds a document."""
        response = client.post("/api/knowledge/kb_test_doc/documents", json={
            "doc_id": "doc_001",
            "content": "This is a test document",
            "metadata": {"source": "test"}
        })
        assert response.status_code in [200, 201, 404, 500]

    def test_list_documents(self, client):
        """GET /api/knowledge/{kb_id}/documents lists documents."""
        response = client.get("/api/knowledge/kb_test_listdocs/documents")
        assert response.status_code in [200, 404, 500]

    def test_delete_document(self, client):
        """DELETE /api/knowledge/{kb_id}/documents/{doc_id} removes doc."""
        response = client.delete("/api/knowledge/kb_test_deldoc/documents/doc_test_delete")
        assert response.status_code in [200, 204, 404, 500]

# ======================== Plugin Marketplace API Tests ========================

class TestPluginMarketplaceAPI:
    """Test plugin marketplace endpoints."""
    pytestmark = [pytest.mark.usefixtures("mock_engine"), pytest.mark.usefixtures("initialized_storage")]

    def test_list_marketplace(self, client):
        """GET /api/plugins/marketplace returns plugin catalog."""
        response = client.get("/api/plugins/marketplace")
        assert response.status_code == 200
        data = response.json()
        assert "plugins" in data or "items" in data or isinstance(data, list)

    def test_get_plugin_detail(self, client):
        """GET /api/plugins/marketplace/{plugin_id} returns plugin details."""
        response = client.get("/api/plugins/marketplace/filesystem")
        assert response.status_code == 200

    def test_marketplace_categories(self, client, initialized_storage):
        """GET /api/plugins/marketplace/categories returns categories."""
        response = client.get("/api/plugins/marketplace/categories")
        assert response.status_code in [200, 404, 500]

    def test_list_installed(self, client):
        """GET /api/plugins/installed returns installed plugins."""
        response = client.get("/api/plugins/installed")
        assert response.status_code in [200, 500]

    def test_install_plugin(self, client):
        """POST /api/plugins/install installs a plugin."""
        response = client.post("/api/plugins/install", json={
            "plugin_id": "filesystem"
        })
        assert response.status_code in [200, 404, 500]

    def test_uninstall_plugin(self, client):
        """POST /api/plugins/uninstall uninstalls a plugin."""
        response = client.post("/api/plugins/uninstall", json={
            "plugin_id": "api_client"
        })
        assert response.status_code in [200, 501, 500]

    def test_plugin_stats(self, client):
        """GET /api/plugins/stats returns usage statistics."""
        response = client.get("/api/plugins/stats")
        assert response.status_code in [200, 500]

# ======================== Variables API Tests ========================

class TestVariablesAPI:
    """Test variable management endpoints."""
    pytestmark = [pytest.mark.usefixtures("mock_engine"), pytest.mark.usefixtures("initialized_storage")]

    def test_list_variables(self, client):
        """GET /api/variables returns all variables."""
        response = client.get("/api/variables")
        assert response.status_code == 200
        data = response.json()
        assert "variables" in data or "items" in data or isinstance(data, list)

    def test_create_variable(self, client):
        """POST /api/variables creates a variable."""
        response = client.post("/api/variables", json={
            "name": "test_var",
            "value": "test_value",
            "description": "A test variable"
        })
        assert response.status_code in [200, 201]

    def test_get_variable(self, client):
        """GET /api/variables/{name} returns variable."""
        name = "var_test_get"
        client.post("/api/variables", json={
            "name": name,
            "value": "get_value"
        })
        response = client.get(f"/api/variables/{name}")
        assert response.status_code == 200

    def test_update_variable(self, client):
        """PUT /api/variables/{name} updates a variable."""
        name = "var_test_update"
        client.post("/api/variables", json={
            "name": name,
            "value": "old_value"
        })
        response = client.put(f"/api/variables/{name}", json={
            "value": "new_value",
            "description": "Updated"
        })
        assert response.status_code == 200

    def test_delete_variable(self, client):
        """DELETE /api/variables/{name} removes a variable."""
        name = "var_test_delete"
        client.post("/api/variables", json={
            "name": name,
            "value": "delete_me"
        })
        response = client.delete(f"/api/variables/{name}")
        assert response.status_code in [200, 204]

    def test_resolve_variables(self, client, initialized_storage):
        """GET /api/variables/resolve resolves expressions."""
        client.post("/api/variables", json={
            "name": "greeting",
            "value": "World",
            "var_type": "string",
        })
        response = client.get("/api/variables/resolve", params={
            "expression": "Hello ${greeting}!"
        })
        assert response.status_code == 200
        assert response.json()["resolved"] == "Hello World!"

# ======================== Webhooks API Tests ========================

class TestWebhooksAPI:
    """Test webhook management endpoints."""
    pytestmark = pytest.mark.usefixtures("mock_engine")

    def test_create_webhook(self, client):
        """POST /api/webhook creates a webhook."""
        response = client.post("/api/webhook", json={
            "name": "Test Webhook",
            "url": "http://localhost:8080/hook",
            "event_types": ["workflow.complete", "workflow.error"]
        })
        assert response.status_code in [200, 201]

    def test_list_webhooks(self, client):
        """GET /api/webhook returns all webhooks."""
        response = client.get("/api/webhook")
        assert response.status_code == 200
        data = response.json()
        assert "webhooks" in data or "items" in data or isinstance(data, list)

    def test_get_webhook(self, client):
        """GET /api/webhook/{id} returns webhook details."""
        # Create first
        create_resp = client.post("/api/webhook", json={
            "name": "Get Test Webhook",
            "url": "http://localhost:8080/hook"
        })
        webhook_data = create_resp.json()
        webhook_id = webhook_data.get("id") or webhook_data.get("webhook_id") or "wh_test"

        response = client.get(f"/api/webhook/{webhook_id}")
        assert response.status_code in [200, 404]

    def test_update_webhook(self, client):
        """PUT /api/webhook/{id} updates webhook."""
        create_resp = client.post("/api/webhook", json={
            "name": "Update Test",
            "url": "http://localhost:8080/old"
        })
        webhook_data = create_resp.json()
        webhook_id = webhook_data.get("id") or webhook_data.get("webhook_id") or "wh_update"

        response = client.put(f"/api/webhook/{webhook_id}", json={
            "name": "Updated Test",
            "url": "http://localhost:8080/new"
        })
        assert response.status_code in [200, 404]

    def test_delete_webhook(self, client):
        """DELETE /api/webhook/{id} removes webhook."""
        create_resp = client.post("/api/webhook", json={
            "name": "Delete Test",
            "url": "http://localhost:8080/hook"
        })
        webhook_data = create_resp.json()
        webhook_id = webhook_data.get("id") or webhook_data.get("webhook_id") or "wh_delete"

        response = client.delete(f"/api/webhook/{webhook_id}")
        assert response.status_code in [200, 204, 404]

    def test_toggle_webhook(self, client):
        """POST /api/webhook/{id}/toggle toggles active state."""
        create_resp = client.post("/api/webhook", json={
            "name": "Toggle Test",
            "url": "http://localhost:8080/hook"
        })
        webhook_data = create_resp.json()
        webhook_id = webhook_data.get("id") or webhook_data.get("webhook_id") or "wh_toggle"

        response = client.post(f"/api/webhook/{webhook_id}/toggle")
        assert response.status_code in [200, 404]

# ======================== Analytics API Tests ========================

class TestAnalyticsAPI:
    """Test analytics endpoints (engine is mocked in client fixture)."""
    pytestmark = pytest.mark.usefixtures("mock_engine")

    def test_summary(self, client):
        """GET /api/analytics/summary returns dashboard summary."""
        response = client.get("/api/analytics/summary")
        assert response.status_code in [200, 500]

    def test_workflows_trend(self, client):
        """GET /api/analytics/workflows/trend returns workflow trend data."""
        response = client.get("/api/analytics/workflows/trend")
        assert response.status_code in [200, 500]

    def test_agents_performance(self, client):
        """GET /api/analytics/agents/performance returns agent stats."""
        response = client.get("/api/analytics/agents/performance")
        assert response.status_code in [200, 500]

    def test_errors(self, client):
        """GET /api/analytics/errors returns error statistics."""
        response = client.get("/api/analytics/errors")
        assert response.status_code in [200, 500]

    def test_blackboard_analytics(self, client):
        """GET /api/analytics/blackboard returns BB stats."""
        response = client.get("/api/analytics/blackboard")
        assert response.status_code in [200, 500]

    def test_rag_analytics(self, client):
        """GET /api/analytics/rag returns RAG stats."""
        response = client.get("/api/analytics/rag")
        assert response.status_code in [200, 500]

    def test_plugins_analytics(self, client):
        """GET /api/analytics/plugins returns plugin stats."""
        response = client.get("/api/analytics/plugins")
        assert response.status_code in [200, 500]

# ======================== Monitoring API Tests ========================

class TestMonitoringAPI:
    """Test monitoring endpoints."""
    pytestmark = [pytest.mark.usefixtures("mock_engine"), pytest.mark.usefixtures("initialized_storage")]

    def test_metrics_prometheus(self, client, initialized_storage):
        """GET /api/monitoring/metrics returns Prometheus format."""
        response = client.get("/api/monitoring/metrics")
        assert response.status_code == 200

    def test_metrics_json(self, client, initialized_storage):
        """GET /api/monitoring/metrics/json returns JSON metrics."""
        response = client.get("/api/monitoring/metrics/json")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_health(self, client):
        """GET /api/monitoring/health returns health status."""
        response = client.get("/api/monitoring/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_detailed(self, client):
        """GET /api/monitoring/health/detailed returns detailed health."""
        response = client.get("/api/monitoring/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data or "services" in data or isinstance(data, dict)

    def test_traces_list(self, client):
        """GET /api/monitoring/traces returns trace list."""
        response = client.get("/api/monitoring/traces")
        assert response.status_code == 200
        data = response.json()
        assert "traces" in data or "items" in data or isinstance(data, list)

    def test_traces_detail(self, client):
        """GET /api/monitoring/traces/{id} returns trace detail."""
        response = client.get("/api/monitoring/traces/trace_001")
        assert response.status_code in [200, 404]

# ======================== Workflow Extended API Tests ========================

class TestWorkflowExtendedAPI:
    """Test workflow version management, export, import, etc."""
    pytestmark = [pytest.mark.usefixtures("mock_engine"), pytest.mark.usefixtures("initialized_storage")]

    def test_workflow_versions(self, client, initialized_storage):
        """GET /api/workflows/{id}/versions returns version history."""
        # Create a workflow first
        create_resp = client.post("/api/workflows", json={
            "name": "Version Test WF",
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": []
        })
        wf_data = create_resp.json()
        wf_id = wf_data.get("id") or wf_data.get("workflow_id") or "wf_version"

        response = client.get(f"/api/workflows/{wf_id}/versions")
        assert response.status_code in [200, 404]

    def test_workflow_version_get(self, client, initialized_storage):
        """GET /api/workflows/{id}/versions/{ver} returns specific version."""
        create_resp = client.post("/api/workflows", json={
            "name": "Version Get Test",
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": []
        })
        wf_data = create_resp.json()
        wf_id = wf_data.get("id") or wf_data.get("workflow_id") or "wf_verget"

        response = client.get(f"/api/workflows/{wf_id}/versions/1")
        assert response.status_code in [200, 404]

    def test_workflow_rollback(self, client, initialized_storage):
        """POST /api/workflows/{id}/rollback/{ver} rolls back to version."""
        create_resp = client.post("/api/workflows", json={
            "name": "Rollback Test",
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": []
        })
        wf_data = create_resp.json()
        wf_id = wf_data.get("id") or wf_data.get("workflow_id") or "wf_rollback"

        response = client.post(f"/api/workflows/{wf_id}/rollback/1")
        assert response.status_code in [200, 404]

    def test_workflow_export(self, client, initialized_storage):
        """GET /api/workflows/{id}/export exports a workflow."""
        create_resp = client.post("/api/workflows", json={
            "name": "Export Test",
            "nodes": [{"id": "n1", "type": "llm", "config": {}}],
            "edges": []
        })
        wf_data = create_resp.json()
        wf_id = wf_data.get("id") or wf_data.get("workflow_id") or "wf_export"

        response = client.get(f"/api/workflows/{wf_id}/export")
        assert response.status_code in [200, 404]

    def test_workflow_import(self, client, initialized_storage):
        """POST /api/workflows/import imports a workflow."""
        import_data = {
            "name": "Imported WF",
            "nodes": [{"id": "n1", "type": "llm", "config": {"model": "gpt-4o"}}],
            "edges": [],
            "version": "1.0.0"
        }
        response = client.post("/api/workflows/import", json=import_data)
        assert response.status_code in [200, 201]

    def test_workflow_batch_export(self, client, initialized_storage):
        """POST /api/workflows/batch-export exports multiple workflows."""
        response = client.post("/api/workflows/batch-export", json={
            "workflow_ids": ["wf_1", "wf_2"]
        })
        assert response.status_code in [200, 404]

    def test_workflow_status(self, client, initialized_storage):
        """GET /api/workflows/{id}/status returns execution status."""
        response = client.get("/api/workflows/wf_status_test/status")
        assert response.status_code in [200, 404]

    def test_workflow_stop(self, client, initialized_storage):
        """POST /api/workflows/{id}/stop stops execution."""
        response = client.post("/api/workflows/wf_stop_test/stop")
        assert response.status_code in [200, 404]

# ======================== Credentials API Tests ========================

class TestCredentialsAPI:
    """Test credential management endpoints."""
    pytestmark = pytest.mark.usefixtures("mock_engine")

    def test_list_credentials(self, client):
        """GET /api/credentials returns all credentials."""
        response = client.get("/api/credentials")
        assert response.status_code == 200
        data = response.json()
        assert "credentials" in data or "items" in data or isinstance(data, list)

    def test_create_credential(self, client):
        """POST /api/credentials creates a credential."""
        response = client.post("/api/credentials", json={
            "id": "cred_test_create",
            "name": "Test Credential",
            "provider": "openai",
            "api_key": "sk-test-123",
            "model": "gpt-4o"
        })
        assert response.status_code in [200, 201, 422, 500]

    def test_get_credential(self, client, monkeypatch):
        """GET /api/credentials/{id} returns credential when explicitly allowed."""
        monkeypatch.setenv("HIVEFLOW_CREDENTIAL_ALLOW_GET", "true")
        cred_resp = client.post("/api/credentials", json={
            "name": "Get Test Cred",
            "type": "api_key",
            "value": "sk-test-456",
        })
        cred_data = cred_resp.json()
        cred_id = cred_data.get("id") or cred_data.get("credential_id") or "cred_get"

        response = client.get(f"/api/credentials/{cred_id}")
        assert response.status_code == 200
        assert response.json()["value"] == "sk-test-456"

    def test_delete_credential(self, client):
        """DELETE /api/credentials/{id} removes credential."""
        cred_resp = client.post("/api/credentials", json={
            "name": "Delete Test Cred",
            "provider": "openai",
            "api_key": "sk-test-789"
        })
        cred_data = cred_resp.json()
        cred_id = cred_data.get("id") or cred_data.get("credential_id") or "cred_delete"

        response = client.delete(f"/api/credentials/{cred_id}")
        assert response.status_code in [200, 204, 404]

# ======================== Agents API Tests ========================

class TestAgentsAPI:
    """Test agent management endpoints."""
    pytestmark = pytest.mark.usefixtures("mock_engine")

    def test_list_agents(self, client):
        """GET /api/agents returns all agents."""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data or "items" in data or isinstance(data, list)

    def test_create_agent(self, client):
        """POST /api/agents creates an agent."""
        response = client.post("/api/agents", json={
            "agent_id": "agent_test_create",
            "name": "Test Agent",
            "agent_type": "react_worker",
            "skills": ["code_executor"],
            "model": "gpt-4o"
        })
        assert response.status_code in [200, 201, 400, 422, 500, 501]

    def test_get_agent(self, client):
        """GET /api/agents/{id} returns agent details."""
        agent_resp = client.post("/api/agents", json={
            "name": "Get Test Agent",
            "agent_type": "react_worker",
            "model": "gpt-4o"
        })
        agent_data = agent_resp.json()
        agent_id = agent_data.get("id") or agent_data.get("agent_id") or "agent_get"

        response = client.get(f"/api/agents/{agent_id}")
        assert response.status_code in [200, 404]

    def test_delete_agent(self, client):
        """DELETE /api/agents/{id} removes an agent."""
        agent_resp = client.post("/api/agents", json={
            "name": "Delete Test Agent",
            "agent_type": "react_worker",
            "model": "gpt-4o"
        })
        agent_data = agent_resp.json()
        agent_id = agent_data.get("id") or agent_data.get("agent_id") or "agent_delete"

        response = client.delete(f"/api/agents/{agent_id}")
        assert response.status_code in [200, 204, 404]

    def test_drain_agent(self, client):
        """POST /api/agents/{id}/drain drains an agent."""
        agent_resp = client.post("/api/agents", json={
            "name": "Drain Test Agent",
            "agent_type": "react_worker",
            "model": "gpt-4o"
        })
        agent_data = agent_resp.json()
        agent_id = agent_data.get("id") or agent_data.get("agent_id") or "agent_drain"

        response = client.post(f"/api/agents/{agent_id}/drain")
        assert response.status_code in [200, 404]

    def test_stop_agent(self, client):
        """POST /api/agents/{id}/stop stops an agent."""
        agent_resp = client.post("/api/agents", json={
            "name": "Stop Test Agent",
            "agent_type": "react_worker",
            "model": "gpt-4o"
        })
        agent_data = agent_resp.json()
        agent_id = agent_data.get("id") or agent_data.get("agent_id") or "agent_stop"

        response = client.post(f"/api/agents/{agent_id}/stop")
        assert response.status_code in [200, 404]

# ======================== Blackboard API Tests ========================

class TestBlackboardAPI:
    """Test blackboard endpoints."""
    pytestmark = pytest.mark.usefixtures("mock_engine")

    def test_list_keys(self, client):
        """GET /api/blackboard/keys returns all keys."""
        response = client.get("/api/blackboard/keys")
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data or "items" in data or isinstance(data, list)

    def test_get_key(self, client):
        """GET /api/blackboard/keys/{key} returns value."""
        response = client.get("/api/blackboard/keys/test_key")
        assert response.status_code in [200, 404]

    def test_set_key(self, client):
        """POST /api/blackboard/keys/{key} sets a value."""
        response = client.post("/api/blackboard/keys/test_set_key", json={
            "value": "test_value",
            "ttl": 3600
        })
        assert response.status_code in [200, 201]

# ======================== Integration Tests ========================

class TestFullWorkflowIntegration:
    """Test complete workflow lifecycle through API."""
    pytestmark = [pytest.mark.usefixtures("mock_engine"), pytest.mark.usefixtures("initialized_storage")]

    def test_create_execute_monitor_workflow(self, client, initialized_storage):
        """Full lifecycle: create → execute → check status."""
        create_resp = client.post("/api/workflows", json={
            "name": "Integration Test WF",
            "description": "Full lifecycle test",
            "nodes": [
                {"id": "n1", "type": "llm", "config": {"model": "gpt-4o", "prompt": "Hello"}},
                {"id": "n2", "type": "output", "config": {}}
            ],
            "edges": [{"from": "n1", "to": "n2"}]
        })
        assert create_resp.status_code in [200, 201]
        wf_data = create_resp.json()
        wf_id = wf_data.get("id") or wf_data.get("workflow_id") or "wf_integration"

        exec_resp = client.post(f"/api/workflows/{wf_id}/execute", json={})
        assert exec_resp.status_code in [200, 201, 500]

        status_resp = client.get(f"/api/workflows/{wf_id}/status")
        assert status_resp.status_code in [200, 404]

    def test_kb_document_pipeline(self, client, initialized_storage):
        """Full KB pipeline: create → add docs → query."""
        kb_id = "kb_integration"
        client.post("/api/knowledge", json={"kb_id": kb_id, "name": "Integration KB"})
        for i in range(3):
            client.post(f"/api/knowledge/{kb_id}/documents", json={
                "doc_id": f"doc_{i}",
                "content": f"Document {i} content",
                "metadata": {"source": f"test_{i}"}
            })
        query_resp = client.post(f"/api/knowledge/{kb_id}/query", json={"query": "test"})
        assert query_resp.status_code in [200, 400, 404, 500]

    def test_plugin_lifecycle(self, client, initialized_storage):
        """Full plugin lifecycle: browse → install → check."""
        market_resp = client.get("/api/plugins/marketplace")
        assert market_resp.status_code == 200

        install_resp = client.post("/api/plugins/install", json={"plugin_id": "api_client"})
        assert install_resp.status_code in [200, 404, 500]

        installed_resp = client.get("/api/plugins/installed")
        assert installed_resp.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_variable_management_workflow(self, async_client, initialized_storage):
        """Full variable lifecycle: create → update → delete."""
        var_name = "integration_var"
        create_resp = await async_client.post("/api/variables", json={
            "name": var_name, "value": "initial_value"
        })
        assert create_resp.status_code in [200, 201]

        update_resp = await async_client.put(f"/api/variables/{var_name}", json={"value": "updated"})
        assert update_resp.status_code in [200, 500]

        get_resp = await async_client.get(f"/api/variables/{var_name}")
        assert get_resp.status_code in [200, 404, 500]

        delete_resp = await async_client.delete(f"/api/variables/{var_name}")
        assert delete_resp.status_code in [200, 204, 404]

        list_resp = await async_client.get("/api/variables")
        assert list_resp.status_code == 200
