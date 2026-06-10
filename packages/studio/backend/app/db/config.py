"""HiveFlow Studio - 数据库配置"""
import os
from typing import Optional

from app.db.base import BaseStorage
from app.db.sqlite_storage import SQLiteStorage

# 可选导入
try:
    from app.db.postgres_storage import PostgreSQLStorage
except ImportError:
    PostgreSQLStorage = None

try:
    from app.db.mongo_storage import MongoDBStorage
except ImportError:
    MongoDBStorage = None

# 全局存储实例
_storage: Optional[BaseStorage] = None


def get_storage() -> BaseStorage:
    """获取当前存储实例"""
    global _storage
    return _storage


async def init_storage() -> None:
    """初始化存储"""
    global _storage

    db_type = os.getenv("HIVEFLOW_DB_TYPE", "sqlite").lower()

    if db_type == "sqlite":
        db_path = os.getenv("HIVEFLOW_DB_PATH", "data/hiveflow.db")
        _storage = SQLiteStorage(db_path=db_path)
    elif db_type == "postgres":
        if not PostgreSQLStorage:
            raise ImportError("PostgreSQL storage requires asyncpg: pip install asyncpg")
        dsn = os.getenv("HIVEFLOW_DB_DSN", "postgresql://postgres:postgres@localhost:5432/hiveflow")
        _storage = PostgreSQLStorage(dsn=dsn)
    elif db_type == "mongo":
        if not MongoDBStorage:
            raise ImportError("MongoDB storage requires motor: pip install motor")
        uri = os.getenv("HIVEFLOW_DB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("HIVEFLOW_DB_NAME", "hiveflow")
        _storage = MongoDBStorage(uri=uri, db_name=db_name)
    else:
        raise ValueError(f"Unknown database type: {db_type}")

    await _storage.initialize()


async def close_storage() -> None:
    """关闭存储"""
    global _storage
    if _storage:
        await _storage.close()
        _storage = None
