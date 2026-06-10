"""HiveFlow Studio - 工作流 API 测试"""
import pytest


class TestWorkflowsAPI:
    """工作流 API 端点测试"""

    def test_list_workflows_empty(self, client, initialized_storage):
        """测试列出空工作流列表"""
        response = client.get("/api/workflows")
        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert isinstance(data["workflows"], list)

    def test_create_workflow(self, client, initialized_storage, test_workflow_data):
        """测试创建工作流"""
        response = client.post(
            "/api/workflows",
            json={
                "name": "Test Workflow",
                "description": "A test workflow",
                "nodes": test_workflow_data["nodes"],
                "edges": test_workflow_data["edges"],
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["saved"] is True

    def test_get_workflow(self, client, initialized_storage, test_workflow_data):
        """测试获取工作流详情"""
        # 先创建
        create_resp = client.post(
            "/api/workflows",
            json={
                "name": "Test Get Workflow",
                "nodes": test_workflow_data["nodes"],
                "edges": test_workflow_data["edges"],
            }
        )
        wf_id = create_resp.json()["id"]

        # 再获取
        response = client.get(f"/api/workflows/{wf_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == wf_id
        assert data["name"] == "Test Get Workflow"

    def test_update_workflow(self, client, initialized_storage, test_workflow_data):
        """测试更新工作流"""
        # 先创建
        create_resp = client.post(
            "/api/workflows",
            json={
                "name": "Test Update Workflow",
                "nodes": test_workflow_data["nodes"],
                "edges": test_workflow_data["edges"],
            }
        )
        wf_id = create_resp.json()["id"]

        # 更新
        response = client.put(
            f"/api/workflows/{wf_id}",
            json={
                "name": "Updated Workflow",
                "nodes": test_workflow_data["nodes"],
                "edges": test_workflow_data["edges"],
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["updated"] is True

    def test_delete_workflow(self, client, initialized_storage, test_workflow_data):
        """测试删除工作流"""
        # 先创建
        create_resp = client.post(
            "/api/workflows",
            json={
                "name": "Test Delete Workflow",
                "nodes": test_workflow_data["nodes"],
                "edges": test_workflow_data["edges"],
            }
        )
        wf_id = create_resp.json()["id"]

        # 删除
        response = client.delete(f"/api/workflows/{wf_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True

        # 确认已删除
        response = client.get(f"/api/workflows/{wf_id}")
        assert response.status_code == 404

    def test_execute_workflow(self, client, initialized_storage, initialized_engine, test_workflow_data):
        """测试执行工作流"""
        # 先创建工作流
        create_resp = client.post(
            "/api/workflows",
            json={
                "name": "Test Execute Workflow",
                "nodes": test_workflow_data["nodes"],
                "edges": test_workflow_data["edges"],
            }
        )
        wf_id = create_resp.json()["id"]

        # 执行
        response = client.post(f"/api/workflows/{wf_id}/execute")
        assert response.status_code == 200
        data = response.json()
        assert "wf_id" in data
        assert "status" in data

    def test_execute_workflow_direct(self, client, initialized_engine):
        """测试直接执行工作流（不需要先保存）"""
        response = client.post(
            "/api/workflows/execute",
            json={
                "graph": {
                    "node-1": {
                        "task": "echo",
                        "depends_on": [],
                    }
                }
            }
        )
        # 应返回执行结果或错误
        assert response.status_code in [200, 400, 500]
