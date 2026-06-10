"""HiveFlow Studio - 数据库抽象层接口"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

# 分页默认限制
DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 1000


@dataclass
class WorkflowRecord:
    """工作流记录"""
    id: str
    name: str = ""
    description: str = ""
    graph: Dict[str, Any] = field(default_factory=dict)
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditRecord:
    """审计日志记录"""
    id: str
    action: str
    entity_type: str  # 'workflow', 'agent', 'blackboard'
    entity_id: str
    user_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


@dataclass
class AgentRecord:
    """Agent 记录"""
    id: str
    name: str
    agent_type: str = ""
    status: str = "active"
    config: Dict[str, Any] = field(default_factory=dict)
    skills: List[str] = field(default_factory=list)
    load: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BaseStorage(ABC):
    """数据库存储抽象基类"""

    @staticmethod
    def _normalize_pagination(limit: int, offset: int) -> tuple:
        """规范化分页参数，防止过大查询"""
        limit = max(1, min(limit, MAX_LIST_LIMIT))
        offset = max(0, offset)
        return limit, offset

    @abstractmethod
    async def initialize(self) -> None:
        """初始化数据库连接和表结构"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭数据库连接"""
        pass

    # ========== 工作流 CRUD ==========

    @abstractmethod
    async def create_workflow(self, workflow: WorkflowRecord) -> str:
        """创建工作流，返回 ID"""
        pass

    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowRecord]:
        """获取工作流"""
        pass

    @abstractmethod
    async def update_workflow(self, workflow_id: str, **kwargs) -> bool:
        """更新工作流"""
        pass

    @abstractmethod
    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        pass

    @abstractmethod
    async def list_workflows(self, limit: int = 100, offset: int = 0) -> List[WorkflowRecord]:
        """列出工作流"""
        pass

    @abstractmethod
    async def get_workflow_versions(self, workflow_id: str) -> List[WorkflowRecord]:
        """获取工作流历史版本"""
        pass

    @abstractmethod
    async def rollback_workflow(self, workflow_id: str, version: int) -> bool:
        """回滚到指定版本"""
        pass

    # ========== Agent CRUD ==========

    @abstractmethod
    async def create_agent(self, agent: AgentRecord) -> str:
        """创建 Agent"""
        pass

    @abstractmethod
    async def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        """获取 Agent"""
        pass

    @abstractmethod
    async def update_agent(self, agent_id: str, **kwargs) -> bool:
        """更新 Agent"""
        pass

    @abstractmethod
    async def delete_agent(self, agent_id: str) -> bool:
        """删除 Agent"""
        pass

    @abstractmethod
    async def list_agents(self, status: Optional[str] = None) -> List[AgentRecord]:
        """列出 Agent"""
        pass

    # ========== 审计日志 ==========

    @abstractmethod
    async def add_audit_log(self, audit: AuditRecord) -> str:
        """添加审计日志"""
        pass

    @abstractmethod
    async def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """获取审计日志"""
        pass

    # ========== 配置存储 ==========

    @abstractmethod
    async def get_config(self, key: str) -> Optional[Any]:
        """获取配置项"""
        pass

    @abstractmethod
    async def set_config(self, key: str, value: Any) -> bool:
        """设置配置项"""
        pass

    @abstractmethod
    async def delete_config(self, key: str) -> bool:
        """删除配置项"""
        pass
