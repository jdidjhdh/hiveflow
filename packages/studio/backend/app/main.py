"""HiveFlow Studio Backend - FastAPI 适配层"""
import asyncio
import os
import sys
import time
import uuid
import contextlib
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Add HiveFlow engine to path
_engine_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.workflows import router as workflows_router
from app.api.agents import router as agents_router
from app.api.blackboard import router as blackboard_router
from app.api.metrics import router as metrics_router
from app.api.events import router as events_router
from app.api.monitoring import router as monitoring_router
from app.api.credentials import router as credentials_router
from app.api.webhooks import router as webhooks_router
from app.api.knowledge import router as knowledge_router
from app.api.plugins import router as plugins_router
from app.api.variables_api import router as variables_router
from app.api.analytics import router as analytics_router
from app.api.prompt_templates import router as prompt_templates_router
from app.api.streaming_api import router as streaming_router
from app.core.engine_service import get_engine
from app.db.config import init_storage, close_storage
from app.api.validation import setup_security_middleware, setup_error_handler, RateLimiter
from hiveflow.observability import setup_structured_logging, create_prometheus_registry
from hiveflow.observability.metrics_prometheus import PrometheusMetricsExporter

# 全局日志器和指标导出器
logger = None
metrics_exporter: PrometheusMetricsExporter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global logger, metrics_exporter
    
    # 初始化结构化日志
    logger = setup_structured_logging(
        level=os.environ.get("HIVEFLOW_LOG_LEVEL", "INFO"),
        service="hiveflow-studio"
    )
    logger.info("HiveFlow Studio starting")
    
    # 记录启动时间
    from app.api.monitoring import set_startup_time
    set_startup_time(time.time())
    
    # 初始化 Prometheus 指标导出器
    metrics_exporter = create_prometheus_registry()
    
    # 初始化存储
    await init_storage()
    
    # 启动引擎
    engine = get_engine()
    await engine.start()
    
    # 注册指标更新回调
    engine.set_metrics_exporter(metrics_exporter)
    
    await engine.subscribe_to_engine_events(
        broadcast_fn=_broadcast_event
    )
    
    logger.info("HiveFlow Studio started successfully")
    
    yield
    
    # 关闭
    logger.info("HiveFlow Studio shutting down")
    await engine.shutdown()
    await close_storage()
    logger.info("HiveFlow Studio stopped")


async def _broadcast_event(topic: str, data: dict):
    """Broadcast engine events to all connected WebSocket clients."""
    from app.core.ws_manager import manager
    await manager.send_event(topic, data)


async def _broadcast_workflow_status(node: str, status: str, result=None):
    """Broadcast workflow node status updates to WebSocket clients."""
    from app.core.ws_manager import manager
    await manager.send_json({
        "type": "workflow.status",
        "node": node,
        "status": status,
        "result": result,
    })


app = FastAPI(title="HiveFlow Studio API", version="0.1.0", lifespan=lifespan)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件：记录每个请求的 method、path、status_code、duration、request_id"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        
        # 将 request_id 放入 request state
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        
        # 跳过静态资源/健康检查的高频日志
        if logger and not request.url.path.startswith(("/api/health", "/favicon")):
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                request_id=request_id,
            )
        
        return response


# 请求日志中间件（最先注册，最后执行）
app.add_middleware(RequestLoggingMiddleware)

# 安全 CORS 配置
allowed_origins = os.environ.get("HIVEFLOW_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)

# 安全中间件与错误处理
rate_limiter = RateLimiter(
    max_requests=int(os.environ.get("HIVEFLOW_RATE_LIMIT", "100")),
    window_seconds=60.0,
)
setup_security_middleware(app, rate_limiter)
setup_error_handler(app)

app.include_router(workflows_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(blackboard_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
app.include_router(credentials_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(plugins_router, prefix="/api")
app.include_router(variables_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(prompt_templates_router, prefix="/api")
app.include_router(streaming_router, prefix="/api")


@app.get("/api/health")
async def health():
    from app.core.engine_service import get_engine
    engine = get_engine()
    return {"status": "ok", "running": engine._running}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from app.core.ws_manager import manager
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "subscribe":
                topics = data.get("topics", [])
                await websocket.send_json({
                    "type": "subscribed",
                    "topics": topics,
                })
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "engine.info":
                engine = get_engine()
                agents = await engine.list_agents()
                metrics = await engine.get_metrics()
                await websocket.send_json({
                    "type": "engine.info",
                    "agents": agents,
                    "metrics": metrics,
                })
            elif msg_type == "engine.stop":
                await engine.shutdown()
                await websocket.send_json({"type": "engine.stopped"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)