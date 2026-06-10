"""HiveFlow Studio - 黑板 API 测试"""
import pytest


class TestBlackboardAPI:
    """黑板 API 端点测试"""

    def test_list_keys_empty(self, client, initialized_engine):
        """测试列出空黑板键"""
        response = client.get("/api/blackboard/keys")
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data

    def test_set_and_get_key(self, client, initialized_engine):
        """测试设置和获取键值"""
        # 设置
        response = client.post(
            "/api/blackboard/keys/test-key",
            json={"value": "test-value"}
        )
        assert response.status_code == 200

        # 获取
        response = client.get("/api/blackboard/keys/test-key")
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "test-value"

    def test_get_nonexistent_key(self, client, initialized_engine):
        """测试获取不存在的键"""
        response = client.get("/api/blackboard/keys/nonexistent-key")
        assert response.status_code == 404

    def test_delete_key(self, client, initialized_engine):
        """测试删除键"""
        # 设置
        client.post(
            "/api/blackboard/keys/delete-test-key",
            json={"value": "delete-me"}
        )

        # 删除
        response = client.delete("/api/blackboard/keys/delete-test-key")
        assert response.status_code == 200

        # 确认已删除
        response = client.get("/api/blackboard/keys/delete-test-key")
        assert response.status_code == 404

    def test_set_key_with_ttl(self, client, initialized_engine):
        """测试设置带 TTL 的键"""
        response = client.post(
            "/api/blackboard/keys/ttl-key",
            json={"value": "ttl-value", "ttl": 60}
        )
        assert response.status_code == 200

    def test_list_audit_log(self, client, initialized_engine):
        """测试列出审计日志"""
        # 先做一些操作
        client.post(
            "/api/blackboard/keys/audit-test-key",
            json={"value": "audit-value"}
        )

        # 获取审计日志
        response = client.get("/api/audit")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data

    def test_list_audit_log_with_filters(self, client, initialized_engine):
        """测试带过滤条件的审计日志"""
        response = client.get("/api/audit?agent=system&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
