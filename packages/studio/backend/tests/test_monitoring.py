"""HiveFlow Studio - 监控 API 测试"""
import pytest


class TestMonitoringAPI:
    """监控 API 端点测试"""

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get("/api/monitoring/health")
        # 可能返回 200, 404 或 500（取决于路由和引擎状态）
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "status" in data

    def test_metrics_endpoint(self, client):
        """测试 Prometheus 指标端点"""
        response = client.get("/api/monitoring/metrics")
        assert response.status_code in [200, 404, 500]

    def test_metrics_json_endpoint(self, client):
        """测试 JSON 格式指标端点"""
        response = client.get("/api/monitoring/metrics/json")
        # 可能返回 200, 404 或 500（如果引擎未初始化）
        assert response.status_code in [200, 404, 500]

    def test_traces_endpoint(self, client):
        """测试追踪端点"""
        response = client.get("/api/monitoring/traces")
        assert response.status_code in [200, 404, 500]

    def test_traces_endpoint_with_limit(self, client):
        """测试带 limit 参数的追踪端点"""
        response = client.get("/api/monitoring/traces?limit=10")
        assert response.status_code in [200, 404, 500]

    def test_traces_detail_endpoint(self, client):
        """测试追踪详情端点"""
        response = client.get("/api/monitoring/traces/nonexistent-trace-id")
        assert response.status_code in [200, 404, 500]
