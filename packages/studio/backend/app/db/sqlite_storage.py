"""HiveFlow Studio - SQLite 存储引擎"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.db.base import (
    AgentRecord, AuditRecord, BaseStorage, WorkflowRecord
)


def _to_iso(dt: datetime) -> str:
    """将 datetime 对象转换为 ISO 格式字符串，避免 SQLite 默认 adapter 警告"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_dt(s: str) -> datetime:
    """将字符串/ISO 格式时间解析为 datetime 对象"""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s))
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


class SQLiteStorage(BaseStorage):
    """SQLite 存储引擎，适合本地开发和小规模部署"""

    def __init__(self, db_path: str = "hiveflow.db"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    async def initialize(self) -> None:
        """初始化数据库连接和表结构"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()

        # 工作流表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                graph TEXT NOT NULL DEFAULT '{}',
                nodes TEXT NOT NULL DEFAULT '[]',
                edges TEXT NOT NULL DEFAULT '[]',
                version INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)

        # 工作流历史版本表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_versions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                graph TEXT NOT NULL DEFAULT '{}',
                nodes TEXT NOT NULL DEFAULT '[]',
                edges TEXT NOT NULL DEFAULT '[]',
                version INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (workflow_id) REFERENCES workflows(id)
            )
        """)

        # Agent 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                agent_type TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                config TEXT NOT NULL DEFAULT '{}',
                skills TEXT NOT NULL DEFAULT '[]',
                load REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 审计日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL DEFAULT '{}',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configs (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_versions_wf ON workflow_versions(workflow_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflows_updated ON workflows(updated_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp DESC)")

        self.conn.commit()

    async def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    # ========== 工作流 CRUD ==========

    async def create_workflow(self, workflow: WorkflowRecord) -> str:
        """创建工作流，返回 ID"""
        now = workflow.created_at or datetime.now(timezone.utc)
        workflow.id = workflow.id or f"wf_{uuid.uuid4().hex[:8]}"

        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO workflows (id, name, description, graph, nodes, edges, version, created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow.id,
                workflow.name,
                workflow.description,
                json.dumps(workflow.graph),
                json.dumps(workflow.nodes),
                json.dumps(workflow.edges),
                workflow.version,
                _to_iso(now),
                _to_iso(now),
                json.dumps(workflow.metadata),
            ),
        )

        # 保存初始版本
        version_id = f"v_{workflow.id}_{workflow.version}"
        cursor.execute(
            """INSERT INTO workflow_versions (id, workflow_id, name, description, graph, nodes, edges, version, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                workflow.id,
                workflow.name,
                workflow.description,
                json.dumps(workflow.graph),
                json.dumps(workflow.nodes),
                json.dumps(workflow.edges),
                workflow.version,
                json.dumps(workflow.metadata),
            ),
        )

        self.conn.commit()
        return workflow.id

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """获取工作流"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return WorkflowRecord(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            graph=json.loads(row["graph"]),
            nodes=json.loads(row["nodes"]),
            edges=json.loads(row["edges"]),
            version=row["version"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            metadata=json.loads(row["metadata"]),
        )

    async def update_workflow(self, workflow_id: str, **kwargs) -> bool:
        """更新工作流"""
        record = await self.get_workflow(workflow_id)
        if not record:
            return False

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = datetime.now(timezone.utc)
        record.version += 1

        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE workflows SET name=?, description=?, graph=?, nodes=?, edges=?, version=?, updated_at=?, metadata=?
               WHERE id=?""",
            (
                record.name,
                record.description,
                json.dumps(record.graph),
                json.dumps(record.nodes),
                json.dumps(record.edges),
                record.version,
                _to_iso(record.updated_at),
                json.dumps(record.metadata),
                workflow_id,
            ),
        )

        # 保存新版本
        version_id = f"v_{workflow_id}_{record.version}"
        cursor.execute(
            """INSERT INTO workflow_versions (id, workflow_id, name, description, graph, nodes, edges, version, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id,
                workflow_id,
                record.name,
                record.description,
                json.dumps(record.graph),
                json.dumps(record.nodes),
                json.dumps(record.edges),
                record.version,
                json.dumps(record.metadata),
            ),
        )

        self.conn.commit()
        return True

    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        cursor.execute("DELETE FROM workflow_versions WHERE workflow_id = ?", (workflow_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    async def list_workflows(self, limit: int = 100, offset: int = 0) -> List[WorkflowRecord]:
        """列出工作流"""
        limit, offset = self._normalize_pagination(limit, offset)
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM workflows ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()

        return [
            WorkflowRecord(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                graph=json.loads(row["graph"]),
                nodes=json.loads(row["nodes"]),
                edges=json.loads(row["edges"]),
                version=row["version"],
                created_at=_parse_dt(row["created_at"]),
                updated_at=_parse_dt(row["updated_at"]),
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    async def get_workflow_versions(self, workflow_id: str) -> List[WorkflowRecord]:
        """获取工作流历史版本"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM workflow_versions WHERE workflow_id = ? ORDER BY version DESC",
            (workflow_id,),
        )
        rows = cursor.fetchall()

        return [
            WorkflowRecord(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                graph=json.loads(row["graph"]),
                nodes=json.loads(row["nodes"]),
                edges=json.loads(row["edges"]),
                version=row["version"],
                created_at=_parse_dt(row["created_at"]),
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    async def rollback_workflow(self, workflow_id: str, version: int) -> bool:
        """回滚到指定版本"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM workflow_versions WHERE workflow_id = ? AND version = ?",
            (workflow_id, version),
        )
        row = cursor.fetchone()

        if not row:
            return False

        # 恢复工作流
        cursor.execute(
            """UPDATE workflows SET name=?, description=?, graph=?, nodes=?, edges=?, version=?, updated_at=?, metadata=?
               WHERE id=?""",
            (
                row["name"],
                row["description"],
                row["graph"],
                row["nodes"],
                row["edges"],
                version + 1,
                _to_iso(datetime.now(timezone.utc)),
                row["metadata"],
                workflow_id,
            ),
        )

        self.conn.commit()
        return True

    # ========== Agent CRUD ==========

    async def create_agent(self, agent: AgentRecord) -> str:
        """创建 Agent"""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO agents (id, name, agent_type, status, config, skills, load)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                agent.id,
                agent.name,
                agent.agent_type,
                agent.status,
                json.dumps(agent.config),
                json.dumps(agent.skills),
                agent.load,
            ),
        )
        self.conn.commit()
        return agent.id

    async def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """获取 Agent"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return AgentRecord(
            id=row["id"],
            name=row["name"],
            agent_type=row["agent_type"],
            status=row["status"],
            config=json.loads(row["config"]),
            skills=json.loads(row["skills"]),
            load=row["load"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    async def update_agent(self, agent_id: str, **kwargs) -> bool:
        """更新 Agent"""
        record = await self.get_agent(agent_id)
        if not record:
            return False

        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = datetime.now(timezone.utc)

        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE agents SET name=?, agent_type=?, status=?, config=?, skills=?, load=?, updated_at=?
               WHERE id=?""",
            (
                record.name,
                record.agent_type,
                record.status,
                json.dumps(record.config),
                json.dumps(record.skills),
                record.load,
                _to_iso(record.updated_at),
                agent_id,
            ),
        )
        self.conn.commit()
        return True

    async def delete_agent(self, agent_id: str) -> bool:
        """删除 Agent"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    async def list_agents(self, status: Optional[str] = None) -> List[AgentRecord]:
        """列出 Agent"""
        cursor = self.conn.cursor()
        if status:
            cursor.execute("SELECT * FROM agents WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT * FROM agents")

        rows = cursor.fetchall()
        return [
            AgentRecord(
                id=row["id"],
                name=row["name"],
                agent_type=row["agent_type"],
                status=row["status"],
                config=json.loads(row["config"]),
                skills=json.loads(row["skills"]),
                load=row["load"],
                created_at=_parse_dt(row["created_at"]),
                updated_at=_parse_dt(row["updated_at"]),
            )
            for row in rows
        ]

    # ========== 审计日志 ==========

    async def add_audit_log(self, audit: AuditRecord) -> str:
        """添加审计日志"""
        audit.id = audit.id or f"audit_{uuid.uuid4().hex[:8]}"
        audit.timestamp = audit.timestamp or datetime.now(timezone.utc)

        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO audit_logs (id, action, entity_type, entity_id, user_id, details, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                audit.id,
                audit.action,
                audit.entity_type,
                audit.entity_id,
                audit.user_id,
                json.dumps(audit.details),
                _to_iso(audit.timestamp),
            ),
        )
        self.conn.commit()
        return audit.id

    async def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """获取审计日志"""
        cursor = self.conn.cursor()

        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [
            AuditRecord(
                id=row["id"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                user_id=row["user_id"],
                details=json.loads(row["details"]),
                timestamp=_parse_dt(row["timestamp"]),
            )
            for row in rows
        ]

    # ========== 配置存储 ==========

    async def get_config(self, key: str) -> Optional[Any]:
        """获取配置项"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM configs WHERE key = ?", (key,))
        row = cursor.fetchone()

        if not row:
            return None

        return json.loads(row["value"])

    async def set_config(self, key: str, value: Any) -> bool:
        """设置配置项"""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO configs (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=?, updated_at=CURRENT_TIMESTAMP""",
            (key, json.dumps(value), json.dumps(value)),
        )
        self.conn.commit()
        return True

    async def delete_config(self, key: str) -> bool:
        """删除配置项"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM configs WHERE key = ?", (key,))
        self.conn.commit()
        return cursor.rowcount > 0
