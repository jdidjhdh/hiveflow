"""HiveFlow Studio Backend - 测试配置"""
import pytest
import pytest_asyncio
import os
import sys
import tempfile

# 添加项目根目录到 Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

# 在导入 app 之前设置环境变量，避免 lifespan 启动引擎
os.environ["HIVEFLOW_DB_TYPE"] = "sqlite"
# 设置极高的速率限制，避免测试触发 429
os.environ["HIVEFLOW_RATE_LIMIT"] = "10000"

from app.main import app
from app.db.config import init_storage, close_storage, get_storage
from app.core.engine_service import get_engine


@pytest.fixture(autouse=True)
def reset_engine_singleton():
    """确保每个测试开始时重置引擎单例，防止测试间污染"""
    import app.core.engine_service as es
    es.engine_service = None
    yield
    es.engine_service = None


@pytest.fixture(autouse=True)
def reset_global_state():
    """清理全局状态（变量存储等）"""
    # 清理变量存储
    try:
        from app.api.variables_api import _variables
        _variables.clear()
    except ImportError:
        pass
    try:
        from app.api.triggers_api import _triggers
        _triggers.clear()
    except ImportError:
        pass
    try:
        from app.core.llm_settings import reset_llm_settings_store
        reset_llm_settings_store()
    except ImportError:
        pass
    try:
        from app.api.credentials import _credentials_store
        _credentials_store.clear()
    except ImportError:
        pass
    yield
    try:
        from app.api.variables_api import _variables
        _variables.clear()
    except ImportError:
        pass
    try:
        from app.api.triggers_api import _triggers
        _triggers.clear()
    except ImportError:
        pass
    try:
        from app.core.llm_settings import reset_llm_settings_store
        reset_llm_settings_store()
    except ImportError:
        pass
    try:
        from app.api.credentials import _credentials_store
        _credentials_store.clear()
    except ImportError:
        pass


@pytest.fixture
def client():
    """创建同步测试客户端（不触发 lifespan）"""
    return TestClient(app, raise_server_exceptions=False)


@pytest_asyncio.fixture
async def async_client():
    """创建异步测试客户端"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_workflow_data():
    """测试工作流数据"""
    return {
        "nodes": [
            {
                "id": "node-1",
                "type": "customNode",
                "position": {"x": 100, "y": 100},
                "data": {
                    "label": "数据输入",
                    "config": {"timeout": 30, "retry": 3}
                }
            },
            {
                "id": "node-2",
                "type": "customNode",
                "position": {"x": 300, "y": 100},
                "data": {
                    "label": "数据处理",
                    "config": {"timeout": 60, "retry": 1}
                }
            },
        ],
        "edges": [
            {
                "id": "edge-1",
                "source": "node-1",
                "target": "node-2",
                "sourceHandle": "output",
                "targetHandle": "input"
            }
        ]
    }


@pytest_asyncio.fixture
async def initialized_storage():
    """初始化和清理测试存储"""
    # 创建临时数据库文件
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    os.environ["HIVEFLOW_DB_PATH"] = db_path
    
    await init_storage()
    yield
    
    await close_storage()
    # 清理临时文件
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest_asyncio.fixture
async def initialized_engine():
    """初始化和清理测试引擎"""
    engine = get_engine()
    await engine.start()
    yield engine
    await engine.shutdown()
    # 重置全局引擎单例
    import app.core.engine_service as es
    es.engine_service = None
