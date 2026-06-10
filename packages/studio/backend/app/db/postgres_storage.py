"""HiveFlow Studio - PostgreSQL 存储引擎"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

from app.db.base import (
    AgentRecord, AuditRecord, BaseStorage, WorkflowRecord
)


class PostgreSQLStorage(BaseStorage):
    """PostgreSQL 存储引擎，适合生产环境"""

    def __init__(self, dsn: str = "postgresql://postgres:postgres@localhost:5432/hiveflow"):
        self.dsn = dsn
        self.pool = None

    async def initialize(self) -> None:
        """初始化数据库连接和表结构"""
        if not HAS_ASYNCPG:
            raise ImportError("asyncpg is required for PostgreSQL storage. Install with: pip install asyncpg")

        self.pool = await asyncpg.create_pool(dsn=self.dsn)

        async with self.pool.acquire() as conn:
            # 工作流表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    graph JSONB NOT NULL DEFAULT '{}',
                    nodes JSONB NOT NULL DEFAULT '[]',
                    edges JSONB NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    metadata JSONB NOT NULL DEFAULT '{}'
                )
            """)

            # 工作流历史版本表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_versions (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL REFERENCES workflows(id),
                    name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    graph JSONB NOT NULL DEFAULT '{}',
                    nodes JSONB NOT NULL DEFAULT '[]',
                    edges JSONB NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    metadata JSONB NOT NULL DEFAULT '{}'
                )
            """)

            # Agent 表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    agent_type TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    config JSONB NOT NULL DEFAULT '{}',
                    skills JSONB NOT NULL DEFAULT '[]',
                    load REAL NOT NULL DEFAULT 0.0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # 审计日志表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT '',
                    details JSONB NOT NULL DEFAULT '{}',
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # 配置表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS configs (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

            # 创建索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_versions_wf ON workflow_versions(workflow_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id)")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self.pool:
            await self.pool.close()
            self.pool = None

    # ========== 工作流 CRUD ==========

    async def create_workflow(self, workflow: WorkflowRecord) -> str:
        """创建工作流，返回 ID"""
        now = workflow.created_at or datetime.now(timezone.utc)
        workflow.id = workflow.id or f"wf_{uuid.uuid4().hex[:8]}"

        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO workflows (id, name, description, graph, nodes, edges, version, created_at, updated_at, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                workflow.id,
                workflow.name,
                workflow.description,
                workflow.graph,
                workflow.nodes,
                workflow.edges,
                workflow.version,
                now,
                now,
                workflow.metadata,
            )

            # 保存初始版本
            version_id = f"v_{workflow.id}_{workflow.version}"
            await conn.execute(
                """INSERT INTO workflow_versions (id, workflow_id, name, description, graph, nodes, edges, version, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                version_id,
                workflow.id,
                workflow.name,
                workflow.description,
                workflow.graph,
                workflow.nodes,
                workflow.edges,
                workflow.version,
                workflow.metadata,
            )

        return workflow.id

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """获取工作流"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM workflows WHERE id = $1", workflow_id)

        if not row:
            return None

        return WorkflowRecord(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            graph=row["graph"],
            nodes=row["nodes"],
            edges=row["edges"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=row["metadata"],
        )

    async def update_workflow(self, workflow_id: str, **kwargs) -> bool:
        """更新工作流"""
        record = await self.get_workflow(workflow_id)
        if not record:
            return False

        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = datetime.now(timezone.utc)
        record.version += 1

        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE workflows SET name=$1, description=$2, graph=$3, nodes=$4, edges=$5, version=$6, updated_at=$7, metadata=$8
                   WHERE id=$9""",
                record.name,
                record.description,
                record.graph,
                record.nodes,
                record.edges,
                record.version,
                record.updated_at,
                record.metadata,
                workflow_id,
            )

            # 保存新版本
            version_id = f"v_{workflow_id}_{record.version}"
            await conn.execute(
                """INSERT INTO workflow_versions (id, workflow_id, name, description, graph, nodes, edges, version, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                version_id,
                workflow_id,
                record.name,
                record.description,
                record.graph,
                record.nodes,
                record.edges,
                record.version,
                record.metadata,
            )

        return True

    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        async with self.pool.acquire() as conn:
            await conn.execute("BEGIN")
            await conn.execute("DELETE FROM workflow_versions WHERE workflow_id = $1", workflow_id)
            result = await conn.execute("DELETE FROM workflows WHERE id = $1", workflow_id)
            await conn.execute("COMMIT")
            return "DELETE" in result

    async def list_workflows(self, limit: int = 100, offset: int = 0) -> List[WorkflowRecord]:
        """列出工作流"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM workflows ORDER BY updated_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )

        return [
            WorkflowRecord(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                graph=row["graph"],
                nodes=row["nodes"],
                edges=row["edges"],
                version=row["version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=row["metadata"],
            )
            for row in rows
        ]

    async def get_workflow_versions(self, workflow_id: str) -> List[WorkflowRecord]:
        """获取工作流历史版本"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM workflow_versions WHERE workflow_id = $1 ORDER BY version DESC",
                workflow_id,
            )

        return [
            WorkflowRecord(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                graph=row["graph"],
                nodes=row["nodes"],
                edges=row["edges"],
                version=row["version"],
                created_at=row["created_at"],
                metadata=row["metadata"],
            )
            for row in rows
        ]

    async def rollback_workflow(self, workflow_id: str, version: int) -> bool:
        """回滚到指定版本"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM workflow_versions WHERE workflow_id = $1 AND version = $2",
                workflow_id, version,
            )

            if not row:
                return False

            await conn.execute(
                """UPDATE workflows SET name=$1, description=$2, graph=$3, nodes=$4, edges=$5, version=$6, updated_at=$7, metadata=$8
                   WHERE id=$9""",
                row["name"],
                row["description"],
                row["graph"],
                row["nodes"],
                row["edges"],
                version + 1,
                datetime.now(timezone.utc),
                row["metadata"],
                workflow_id,
            )

        return True

    # ========== Agent CRUD ==========

    async def create_agent(self, agent: AgentRecord) -> str:
        """创建 Agent"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO agents (id, name, agent_type, status, config, skills, load)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                agent.id,
                agent.name,
                agent.agent_type,
                agent.status,
                agent.config,
                agent.skills,
                agent.load,
            )
        return agent.id

    async def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """获取 Agent"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM agents WHERE id = $1", agent_id)

        if not row:
            return None

        return AgentRecord(
            id=row["id"],
            name=row["name"],
            agent_type=row["agent_type"],
            status=row["status"],
            config=row["config"],
            skills=row["skills"],
            load=row["load"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
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

        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE agents SET name=$1, agent_type=$2, status=$3, config=$4, skills=$5, load=$6, updated_at=$7
                   WHERE id=$8""",
                record.name,
                record.agent_type,
                record.status,
                record.config,
                record.skills,
                record.load,
                record.updated_at,
                agent_id,
            )
        return True

    async def delete_agent(self, agent_id: str) -> bool:
        """删除 Agent"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM agents WHERE id = $1", agent_id)
            return "DELETE" in result

    async def list_agents(self, status: Optional[str] = None) -> List[AgentRecord]:
        """列出 Agent"""
        async with self.pool.acquire() as conn:
            if status:
                rows = await conn.fetch("SELECT * FROM agents WHERE status = $1", status)
            else:
                rows = await conn.fetch("SELECT * FROM agents")

        return [
            AgentRecord(
                id=row["id"],
                name=row["name"],
                agent_type=row["agent_type"],
                status=row["status"],
                config=row["config"],
                skills=row["skills"],
                load=row["load"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    # ========== 审计日志 ==========

    async def add_audit_log(self, audit: AuditRecord) -> str:
        """添加审计日志"""
        audit.id = audit.id or f"audit_{uuid.uuid4().hex[:8]}"
        audit.timestamp = audit.timestamp or datetime.now(timezone.utc)

        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO audit_logs (id, action, entity_type, entity_id, user_id, details, timestamp)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                audit.id,
                audit.action,
                audit.entity_type,
                audit.entity_id,
                audit.user_id,
                audit.details,
                audit.timestamp,
            )
        return audit.id

    async def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """获取审计日志"""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if entity_type:
            query += f" AND entity_type = ${len(params) + 1}"
            params.append(entity_type)
        if entity_id:
            query += f" AND entity_id = ${len(params) + 1}"
            params.append(entity_id)

        query += f" ORDER BY timestamp DESC LIMIT ${len(params) + 1}"
        params.append(limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            AuditRecord(
                id=row["id"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                user_id=row["user_id"],
                details=row["details"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    # ========== 配置存储 ==========

    async def get_config(self, key: str) -> Optional[Any]:
        """获取配置项"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM configs WHERE key = $1", key)
        return row["value"] if row else None

    async def set_config(self, key: str, value: Any) -> bool:
        """设置配置项"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO configs (key, value) VALUES ($1, $2)
                   ON CONFLICT(key) DO UPDATE SET value=$2, updated_at=NOW()""",
                key, value,
            )
        return True

    async def delete_config(self, key: str) -> bool:
        """删除配置项"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM configs WHERE key = $1", key)
            return "DELETE" in result
