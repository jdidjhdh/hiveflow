"""HiveFlow Studio - 请求验证与安全中间件"""
import logging
import time
from collections import defaultdict
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# ========== Pydantic 请求模型 ==========

MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_NODES = 500
MAX_GRAPH_SIZE = 100_000  # characters


class WorkflowCreateRequest(BaseModel):
    """创建工作流请求验证"""
    id: Optional[str] = None
    name: str = ""
    description: str = ""
    graph: Dict[str, Any] = {}
    nodes: list = []
    edges: list = []
    metadata: Dict[str, Any] = {}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"Name too long (max {MAX_NAME_LENGTH} chars)")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        if len(v) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description too long (max {MAX_DESCRIPTION_LENGTH} chars)")
        return v

    @field_validator("nodes")
    @classmethod
    def validate_nodes(cls, v: list) -> list:
        if len(v) > MAX_NODES:
            raise ValueError(f"Too many nodes (max {MAX_NODES})")
        return v

    @field_validator("graph")
    @classmethod
    def validate_graph_size(cls, v: Dict) -> Dict:
        import json
        if len(json.dumps(v)) > MAX_GRAPH_SIZE:
            raise ValueError(f"Graph too large (max {MAX_GRAPH_SIZE} chars)")
        return v


class WorkflowUpdateRequest(BaseModel):
    """更新工作流请求验证"""
    name: Optional[str] = None
    description: Optional[str] = None
    graph: Optional[Dict[str, Any]] = None
    nodes: Optional[list] = None
    edges: Optional[list] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"Name too long (max {MAX_NAME_LENGTH} chars)")
        return v.strip() if v else v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description too long (max {MAX_DESCRIPTION_LENGTH} chars)")
        return v

    @field_validator("nodes")
    @classmethod
    def validate_nodes(cls, v: Optional[list]) -> Optional[list]:
        if v is not None and len(v) > MAX_NODES:
            raise ValueError(f"Too many nodes (max {MAX_NODES})")
        return v


class AgentCreateRequest(BaseModel):
    """创建 Agent 请求验证"""
    id: Optional[str] = None
    name: str
    agent_type: str = "default"
    skills: list = []
    config: Dict[str, Any] = {}

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Agent name cannot be empty")
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"Name too long (max {MAX_NAME_LENGTH} chars)")
        return v

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Agent type cannot be empty")
        return v


class BlackboardSetRequest(BaseModel):
    """黑板写入请求验证"""
    key: str
    value: Any
    ttl: Optional[float] = None

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Key cannot be empty")
        if len(v) > 200:
            raise ValueError("Key too long (max 200 chars)")
        return v


class ExecuteWorkflowRequest(BaseModel):
    """执行工作流请求验证"""
    graph: Dict[str, Any]
    global_timeout: Optional[float] = 300.0

    @field_validator("graph")
    @classmethod
    def validate_graph(cls, v: Dict) -> Dict:
        import json
        if not v:
            raise ValueError("Graph cannot be empty")
        if len(json.dumps(v)) > MAX_GRAPH_SIZE:
            raise ValueError(f"Graph too large (max {MAX_GRAPH_SIZE} chars)")
        return v

    @field_validator("global_timeout")
    @classmethod
    def validate_timeout(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v <= 0 or v > 3600):
            raise ValueError("Timeout must be between 0 and 3600 seconds")
        return v


# ========== 简单内存速率限制器 ==========

class RateLimiter:
    """基于内存的简单速率限制器"""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        # 清理过期记录
        self._requests[client_ip] = [
            t for t in self._requests[client_ip]
            if now - t < self.window_seconds
        ]
        if len(self._requests[client_ip]) >= self.max_requests:
            return False
        self._requests[client_ip].append(now)
        return True


# ========== 中间件 ==========

def setup_security_middleware(app: FastAPI, rate_limiter: Optional[RateLimiter] = None):
    """安装安全中间件"""

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        """添加安全响应头"""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store"
        return response

    if rate_limiter:
        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            """速率限制中间件"""
            client_ip = request.client.host if request.client else "unknown"
            # 跳过健康检查
            if request.url.path in ("/api/health", "/health"):
                return await call_next(request)
            if not rate_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded. Please try again later."},
                )
            return await call_next(request)


def setup_error_handler(app: FastAPI):
    """安装统一错误处理"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(
            "HTTP error: %s %s -> %s",
            request.method, request.url.path, exc.detail
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning("Validation error: %s %s -> %s", request.method, request.url.path, str(exc))
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )
