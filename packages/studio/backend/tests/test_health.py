"""HiveFlow Studio - 健康检查和基础 API 测试"""
import pytest


class TestHealthCheck:
    """健康检查端点测试"""

    def test_health_endpoint(self, client):
        """测试 /api/health 端点返回正常状态"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_endpoint_contains_running_flag(self, client):
        """测试健康检查包含 running 标志"""
        response = client.get("/api/health")
        data = response.json()
        assert "running" in data
        assert isinstance(data["running"], bool)
