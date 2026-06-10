"""HiveFlow Studio - 验证与安全中间件测试"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient
from app.api.validation import (
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
    AgentCreateRequest,
    BlackboardSetRequest,
    ExecuteWorkflowRequest,
    RateLimiter,
    setup_security_middleware,
    setup_error_handler,
    MAX_NAME_LENGTH,
    MAX_NODES,
    MAX_GRAPH_SIZE,
)


class TestWorkflowCreateRequest:
    """工作流创建请求验证测试"""

    def test_valid_request(self):
        req = WorkflowCreateRequest(name="Test Workflow", nodes=[], edges=[])
        assert req.name == "Test Workflow"
        assert req.nodes == []

    def test_name_too_long(self):
        with pytest.raises(ValueError, match="Name too long"):
            WorkflowCreateRequest(name="x" * (MAX_NAME_LENGTH + 1))

    def test_name_stripped(self):
        req = WorkflowCreateRequest(name="  Test  ")
        assert req.name == "Test"

    def test_description_too_long(self):
        with pytest.raises(ValueError, match="Description too long"):
            WorkflowCreateRequest(description="x" * 3000)

    def test_too_many_nodes(self):
        with pytest.raises(ValueError, match="Too many nodes"):
            WorkflowCreateRequest(nodes=[{"id": str(i)} for i in range(MAX_NODES + 1)])

    def test_graph_too_large(self):
        with pytest.raises(ValueError, match="Graph too large"):
            WorkflowCreateRequest(graph={"data": "x" * (MAX_GRAPH_SIZE + 1)})


class TestAgentCreateRequest:
    """Agent 创建请求验证测试"""

    def test_valid_request(self):
        req = AgentCreateRequest(name="TestAgent")
        assert req.name == "TestAgent"
        assert req.agent_type == "default"

    def test_empty_name(self):
        with pytest.raises(ValueError, match="name cannot be empty"):
            AgentCreateRequest(name="   ")

    def test_empty_agent_type(self):
        with pytest.raises(ValueError, match="type cannot be empty"):
            AgentCreateRequest(name="Test", agent_type="   ")


class TestBlackboardSetRequest:
    """黑板写入请求验证测试"""

    def test_valid_request(self):
        req = BlackboardSetRequest(key="test_key", value="test_value")
        assert req.key == "test_key"

    def test_empty_key(self):
        with pytest.raises(ValueError, match="Key cannot be empty"):
            BlackboardSetRequest(key="   ", value="val")

    def test_key_too_long(self):
        with pytest.raises(ValueError, match="Key too long"):
            BlackboardSetRequest(key="x" * 201, value="val")


class TestExecuteWorkflowRequest:
    """执行工作流请求验证测试"""

    def test_valid_request(self):
        req = ExecuteWorkflowRequest(graph={"node1": {"task": "test"}})
        assert req.graph == {"node1": {"task": "test"}}
        assert req.global_timeout == 300.0

    def test_empty_graph(self):
        with pytest.raises(ValueError, match="Graph cannot be empty"):
            ExecuteWorkflowRequest(graph={})

    def test_timeout_too_high(self):
        with pytest.raises(ValueError, match="between 0 and 3600"):
            ExecuteWorkflowRequest(graph={"n": {}}, global_timeout=3601)

    def test_timeout_negative(self):
        with pytest.raises(ValueError, match="between 0 and 3600"):
            ExecuteWorkflowRequest(graph={"n": {}}, global_timeout=-1)


class TestRateLimiter:
    """速率限制器测试"""

    def test_basic_allow(self):
        limiter = RateLimiter(max_requests=10)
        assert limiter.is_allowed("127.0.0.1") is True

    def test_rate_limit_exceeded(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60.0)
        assert limiter.is_allowed("127.0.0.1") is True
        assert limiter.is_allowed("127.0.0.1") is True
        assert limiter.is_allowed("127.0.0.1") is False

    def test_window_expiry(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.001)
        assert limiter.is_allowed("127.0.0.1") is True
        assert limiter.is_allowed("127.0.0.1") is False
        import time
        time.sleep(0.002)
        assert limiter.is_allowed("127.0.0.1") is True

    def test_different_ips(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60.0)
        assert limiter.is_allowed("1.1.1.1") is True
        assert limiter.is_allowed("2.2.2.2") is True


class TestSecurityMiddleware:
    """安全中间件测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        setup_security_middleware(app)
        setup_error_handler(app)
        return app

    def test_security_headers(self, app):
        """测试安全响应头"""
        client = TestClient(app)
        response = client.get("/test")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    def test_error_handler_returns_json(self, app):
        """测试错误处理返回 JSON"""
        client = TestClient(app)
        # 404 应该返回 JSON (FastAPI 默认使用 'detail' key)
        response = client.get("/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert isinstance(data, dict)
        assert "detail" in data or "error" in data


class TestPaginationNormalization:
    """分页参数规范化测试"""

    def test_normal_params(self):
        from app.db.base import BaseStorage
        limit, offset = BaseStorage._normalize_pagination(50, 10)
        assert limit == 50
        assert offset == 10

    def test_limit_capped(self):
        from app.db.base import BaseStorage, MAX_LIST_LIMIT
        limit, offset = BaseStorage._normalize_pagination(9999, 0)
        assert limit == MAX_LIST_LIMIT

    def test_negative_offset(self):
        from app.db.base import BaseStorage
        limit, offset = BaseStorage._normalize_pagination(10, -5)
        assert offset == 0

    def test_zero_limit(self):
        from app.db.base import BaseStorage
        limit, offset = BaseStorage._normalize_pagination(0, 0)
        assert limit == 1  # minimum 1
