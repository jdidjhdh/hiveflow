"""HiveFlow Studio - MongoDB 存储引擎"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    HAS_MOTOR = True
except ImportError:
    HAS_MOTOR = False

from app.db.base import (
    AgentRecord, AuditRecord, BaseStorage, WorkflowRecord
)


class MongoDBStorage(BaseStorage):
    """MongoDB 存储引擎，适合文档存储和水平扩展"""

    def __init__(self, uri: str = "mongodb://localhost:27017", db_name: str = "hiveflow"):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None

    async def initialize(self) -> None:
        """初始化数据库连接"""
        if not HAS_MOTOR:
            raise ImportError("motor is required for MongoDB storage. Install with: pip install motor")

        self.client = AsyncIOMotorClient(self.uri)
        self.db = self.client[self.db_name]

        # 创建索引
        await self.db.workflows.create_index("id", unique=True)
        await self.db.workflow_versions.create_index("workflow_id")
        await self.db.workflow_versions.create_index([("workflow_id", 1), ("version", 1)], unique=True)
        await self.db.agents.create_index("id", unique=True)
        await self.db.audit_logs.create_index([("entity_type", 1), ("entity_id", 1)])
        await self.db.configs.create_index("key", unique=True)

    async def close(self) -> None:
        """关闭数据库连接"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    # ========== 工作流 CRUD ==========

    async def create_workflow(self, workflow: WorkflowRecord) -> str:
        """创建工作流，返回 ID"""
        now = workflow.created_at or datetime.now(timezone.utc)
        workflow.id = workflow.id or f"wf_{uuid.uuid4().hex[:8]}"

        doc = {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "graph": workflow.graph,
            "nodes": workflow.nodes,
            "edges": workflow.edges,
            "version": workflow.version,
            "created_at": now,
            "updated_at": now,
            "metadata": workflow.metadata,
        }

        await self.db.workflows.insert_one(doc)

        # 保存初始版本
        version_doc = {
            "id": f"v_{workflow.id}_{workflow.version}",
            "workflow_id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "graph": workflow.graph,
            "nodes": workflow.nodes,
            "edges": workflow.edges,
            "version": workflow.version,
            "created_at": now,
            "metadata": workflow.metadata,
        }
        await self.db.workflow_versions.insert_one(version_doc)

        return workflow.id

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """获取工作流"""
        doc = await self.db.workflows.find_one({"id": workflow_id})
        if not doc:
            return None

        return self._doc_to_workflow(doc)

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

        update_data = {
            "name": record.name,
            "description": record.description,
            "graph": record.graph,
            "nodes": record.nodes,
            "edges": record.edges,
            "version": record.version,
            "updated_at": record.updated_at,
            "metadata": record.metadata,
        }

        await self.db.workflows.update_one(
            {"id": workflow_id},
            {"$set": update_data},
        )

        # 保存新版本
        version_doc = {
            "id": f"v_{workflow_id}_{record.version}",
            "workflow_id": workflow_id,
            "name": record.name,
            "description": record.description,
            "graph": record.graph,
            "nodes": record.nodes,
            "edges": record.edges,
            "version": record.version,
            "created_at": datetime.now(timezone.utc),
            "metadata": record.metadata,
        }
        await self.db.workflow_versions.insert_one(version_doc)

        return True

    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        result = await self.db.workflows.delete_one({"id": workflow_id})
        await self.db.workflow_versions.delete_many({"workflow_id": workflow_id})
        return result.deleted_count > 0

    async def list_workflows(self, limit: int = 100, offset: int = 0) -> List[WorkflowRecord]:
        """列出工作流"""
        cursor = self.db.workflows.find().sort("updated_at", -1).skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self._doc_to_workflow(doc) for doc in docs]

    async def get_workflow_versions(self, workflow_id: str) -> List[WorkflowRecord]:
        """获取工作流历史版本"""
        cursor = self.db.workflow_versions.find(
            {"workflow_id": workflow_id}
        ).sort("version", -1)
        docs = await cursor.to_list(length=None)
        return [self._doc_to_workflow(doc) for doc in docs]

    async def rollback_workflow(self, workflow_id: str, version: int) -> bool:
        """回滚到指定版本"""
        doc = await self.db.workflow_versions.find_one({
            "workflow_id": workflow_id,
            "version": version,
        })

        if not doc:
            return False

        update_data = {
            "name": doc["name"],
            "description": doc["description"],
            "graph": doc["graph"],
            "nodes": doc["nodes"],
            "edges": doc["edges"],
            "version": version + 1,
            "updated_at": datetime.now(timezone.utc),
            "metadata": doc["metadata"],
        }

        await self.db.workflows.update_one(
            {"id": workflow_id},
            {"$set": update_data},
        )

        return True

    # ========== Agent CRUD ==========

    async def create_agent(self, agent: AgentRecord) -> str:
        """创建 Agent"""
        doc = {
            "id": agent.id,
            "name": agent.name,
            "agent_type": agent.agent_type,
            "status": agent.status,
            "config": agent.config,
            "skills": agent.skills,
            "load": agent.load,
            "created_at": agent.created_at or datetime.now(timezone.utc),
            "updated_at": agent.updated_at or datetime.now(timezone.utc),
        }
        await self.db.agents.insert_one(doc)
        return agent.id

    async def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """获取 Agent"""
        doc = await self.db.agents.find_one({"id": agent_id})
        if not doc:
            return None
        return self._doc_to_agent(doc)

    async def update_agent(self, agent_id: str, **kwargs) -> bool:
        """更新 Agent"""
        record = await self.get_agent(agent_id)
        if not record:
            return False

        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)

        record.updated_at = datetime.now(timezone.utc)

        await self.db.agents.update_one(
            {"id": agent_id},
            {"$set": {
                "name": record.name,
                "agent_type": record.agent_type,
                "status": record.status,
                "config": record.config,
                "skills": record.skills,
                "load": record.load,
                "updated_at": record.updated_at,
            }},
        )
        return True

    async def delete_agent(self, agent_id: str) -> bool:
        """删除 Agent"""
        result = await self.db.agents.delete_one({"id": agent_id})
        return result.deleted_count > 0

    async def list_agents(self, status: Optional[str] = None) -> List[AgentRecord]:
        """列出 Agent"""
        query = {"status": status} if status else {}
        cursor = self.db.agents.find(query)
        docs = await cursor.to_list(length=None)
        return [self._doc_to_agent(doc) for doc in docs]

    # ========== 审计日志 ==========

    async def add_audit_log(self, audit: AuditRecord) -> str:
        """添加审计日志"""
        audit.id = audit.id or f"audit_{uuid.uuid4().hex[:8]}"
        audit.timestamp = audit.timestamp or datetime.now(timezone.utc)

        doc = {
            "id": audit.id,
            "action": audit.action,
            "entity_type": audit.entity_type,
            "entity_id": audit.entity_id,
            "user_id": audit.user_id,
            "details": audit.details,
            "timestamp": audit.timestamp,
        }
        await self.db.audit_logs.insert_one(doc)
        return audit.id

    async def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """获取审计日志"""
        query = {}
        if entity_type:
            query["entity_type"] = entity_type
        if entity_id:
            query["entity_id"] = entity_id

        cursor = self.db.audit_logs.find(query).sort("timestamp", -1).limit(limit)
        docs = await cursor.to_list(length=limit)

        return [
            AuditRecord(
                id=doc["id"],
                action=doc["action"],
                entity_type=doc["entity_type"],
                entity_id=doc["entity_id"],
                user_id=doc.get("user_id", ""),
                details=doc.get("details", {}),
                timestamp=doc["timestamp"],
            )
            for doc in docs
        ]

    # ========== 配置存储 ==========

    async def get_config(self, key: str) -> Optional[Any]:
        """获取配置项"""
        doc = await self.db.configs.find_one({"key": key})
        return doc["value"] if doc else None

    async def set_config(self, key: str, value: Any) -> bool:
        """设置配置项"""
        await self.db.configs.update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return True

    async def delete_config(self, key: str) -> bool:
        """删除配置项"""
        result = await self.db.configs.delete_one({"key": key})
        return result.deleted_count > 0

    # ========== 辅助方法 ==========

    @staticmethod
    def _doc_to_workflow(doc: Dict[str, Any]) -> WorkflowRecord:
        """将 MongoDB 文档转换为 WorkflowRecord"""
        return WorkflowRecord(
            id=doc["id"],
            name=doc.get("name", ""),
            description=doc.get("description", ""),
            graph=doc.get("graph", {}),
            nodes=doc.get("nodes", []),
            edges=doc.get("edges", []),
            version=doc.get("version", 1),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            metadata=doc.get("metadata", {}),
        )

    @staticmethod
    def _doc_to_agent(doc: Dict[str, Any]) -> AgentRecord:
        """将 MongoDB 文档转换为 AgentRecord"""
        return AgentRecord(
            id=doc["id"],
            name=doc["name"],
            agent_type=doc.get("agent_type", ""),
            status=doc.get("status", "active"),
            config=doc.get("config", {}),
            skills=doc.get("skills", []),
            load=doc.get("load", 0.0),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )
