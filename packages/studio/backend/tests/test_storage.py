"""HiveFlow Studio - 数据库持久化测试"""
import pytest
import pytest_asyncio
import os
import tempfile

# 添加项目根目录到 Python path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import WorkflowRecord
from app.db.config import init_storage, close_storage, get_storage


class TestStorageConfig:
    """存储配置测试"""

    @pytest.mark.asyncio
    async def test_init_storage(self):
        """测试存储初始化"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
            os.environ["HIVEFLOW_DB_PATH"] = db_path
            await init_storage()
            storage = get_storage()
            assert storage is not None
            await close_storage()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_get_storage_singleton(self):
        """测试存储单例模式"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
            os.environ["HIVEFLOW_DB_PATH"] = db_path
            await init_storage()
            storage1 = get_storage()
            storage2 = get_storage()
            assert storage1 is storage2
            await close_storage()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestWorkflowStorage:
    """工作流存储测试"""

    @pytest.mark.asyncio
    async def test_save_workflow(self):
        """测试保存工作流"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
            os.environ["HIVEFLOW_DB_PATH"] = db_path
            await init_storage()
            storage = get_storage()

            workflow = WorkflowRecord(
                id="test-wf-1",
                name="Test Workflow",
                description="A test workflow",
                graph={"nodes": [], "edges": []},
                nodes=[],
                edges=[],
                metadata={"version": 1},
            )
            result = await storage.create_workflow(workflow)
            assert result is not None
            await close_storage()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_get_workflow(self):
        """测试获取工作流"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
            os.environ["HIVEFLOW_DB_PATH"] = db_path
            await init_storage()
            storage = get_storage()

            workflow = WorkflowRecord(
                id="test-wf-2",
                name="Test Get Workflow",
                description="A test workflow",
                graph={"nodes": [], "edges": []},
                nodes=[],
                edges=[],
                metadata={"version": 1},
            )
            await storage.create_workflow(workflow)

            result = await storage.get_workflow("test-wf-2")
            assert result is not None
            assert result.name == "Test Get Workflow"
            await close_storage()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_list_workflows(self):
        """测试列出工作流"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
            os.environ["HIVEFLOW_DB_PATH"] = db_path
            await init_storage()
            storage = get_storage()

            workflow = WorkflowRecord(
                id="test-wf-3",
                name="Test List Workflow",
                description="A test workflow",
                graph={"nodes": [], "edges": []},
                nodes=[],
                edges=[],
                metadata={"version": 1},
            )
            await storage.create_workflow(workflow)

            workflows = await storage.list_workflows()
            assert isinstance(workflows, list)
            await close_storage()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_delete_workflow(self):
        """测试删除工作流"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
            os.environ["HIVEFLOW_DB_PATH"] = db_path
            await init_storage()
            storage = get_storage()

            workflow = WorkflowRecord(
                id="test-wf-4",
                name="Test Delete Workflow",
                description="A test workflow",
                graph={"nodes": [], "edges": []},
                nodes=[],
                edges=[],
                metadata={"version": 1},
            )
            await storage.create_workflow(workflow)

            await storage.delete_workflow("test-wf-4")
            result = await storage.get_workflow("test-wf-4")
            assert result is None
            await close_storage()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestVersionStorage:
    """版本存储测试"""

    @pytest.mark.asyncio
    async def test_save_workflow_version(self):
        """测试保存工作流版本"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
            os.environ["HIVEFLOW_DB_PATH"] = db_path
            await init_storage()
            storage = get_storage()

            workflow = WorkflowRecord(
                id="test-wf-5",
                name="Test Version Workflow",
                description="A test workflow",
                graph={"nodes": [], "edges": []},
                nodes=[],
                edges=[],
                metadata={"version": 1},
            )
            await storage.create_workflow(workflow)

            await storage.update_workflow(
                "test-wf-5",
                graph={"nodes": [], "edges": []},
                metadata={"version": 2},
            )

            versions = await storage.get_workflow_versions("test-wf-5")
            assert len(versions) >= 1
            await close_storage()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
