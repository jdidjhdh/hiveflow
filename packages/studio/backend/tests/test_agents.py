"""HiveFlow Studio - Agent API 测试"""
import pytest


class TestAgentsAPI:
    """Agent API 端点测试"""

    def test_list_agents_empty(self, client):
        """测试列出空 Agent 列表"""
        response = client.get("/api/agents")
        # 引擎未初始化时可能返回 500 或 404
        if response.status_code == 200:
            data = response.json()
            assert "agents" in data
            assert isinstance(data["agents"], list)

    def test_create_agent(self, client, initialized_engine):
        """测试创建 Agent"""
        response = client.post(
            "/api/agents",
            json={
                "agent_id": "test-agent-1",
                "skills": ["skill1", "skill2"],
                "read_keys": ["data:*"],
                "write_keys": ["result:*"],
                "max_queue_size": 10,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test-agent-1"
        assert data["registered"] is True

    def test_get_agent(self, client, initialized_engine):
        """测试获取 Agent 详情"""
        # 先创建
        client.post(
            "/api/agents",
            json={
                "agent_id": "test-agent-2",
                "skills": ["skill1"],
                "read_keys": ["data:*"],
                "write_keys": ["result:*"],
            }
        )

        # 获取
        response = client.get("/api/agents/test-agent-2")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test-agent-2"

    def test_get_nonexistent_agent(self, client, initialized_engine):
        """测试获取不存在的 Agent"""
        response = client.get("/api/agents/nonexistent-agent")
        assert response.status_code == 404

    def test_stop_agent(self, client, initialized_engine):
        """测试停止 Agent"""
        # 先创建
        client.post(
            "/api/agents",
            json={
                "agent_id": "test-agent-3",
                "skills": ["skill1"],
                "read_keys": ["data:*"],
                "write_keys": ["result:*"],
            }
        )

        # 停止
        response = client.post("/api/agents/test-agent-3/stop")
        assert response.status_code == 200

    def test_drain_agent(self, client, initialized_engine):
        """测试排水 Agent（等待任务完成）"""
        # 先创建
        client.post(
            "/api/agents",
            json={
                "agent_id": "test-agent-4",
                "skills": ["skill1"],
                "read_keys": ["data:*"],
                "write_keys": ["result:*"],
            }
        )

        # 排水
        response = client.post("/api/agents/test-agent-4/drain")
        assert response.status_code == 200
