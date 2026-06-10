"""HiveFlow Core - OpenTelemetry 分布式追踪

集成 OpenTelemetry 实现跨服务追踪:
- 自动追踪工作流执行链路
- 追踪 Agent 间的消息传递
- 追踪黑板操作
- 追踪 LLM 调用

使用方式:
    from hiveflow.observability import setup_tracing, create_span

    # 初始化追踪
    tracer = setup_tracing(service_name="hiveflow-core")

    # 创建 span
    with tracer.start_as_current_span("workflow.execute", attributes={"workflow_id": "wf-123"}):
        # 执行工作流
        pass

    # 或使用装饰器
    @tracer.trace("task.execute")
    async def execute_task(task_id):
        pass

环境要求:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp

环境变量:
    OTEL_SERVICE_NAME: 服务名称 (默认: hiveflow)
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP 端点 (默认: http://localhost:4318)
    OTEL_TRACES_SAMPLER: 采样器 (默认: parentbased_always_on)
    OTEL_TRACES_SAMPLER_ARG: 采样率 (0.0-1.0, 默认: 1.0)
"""

import os
import time
import functools
from typing import Any, Dict, Optional, Callable
from contextlib import contextmanager


class Span:
    """简化的 Span 实现 (不依赖 OpenTelemetry SDK)"""

    def __init__(self, name: str, parent: Optional['Span'] = None, attributes: Dict[str, Any] = None):
        self.name = name
        self.parent = parent
        self.attributes = attributes or {}
        self.start_time = time.perf_counter()
        self.end_time = None
        self.status = "unset"
        self.events = []

        # 生成 trace_id 和 span_id
        import uuid
        if parent and parent.trace_id:
            self.trace_id = parent.trace_id
        else:
            self.trace_id = uuid.uuid4().hex
        self.span_id = uuid.uuid4().hex[:16]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        if exc_type is not None:
            self.status = "error"
            self.attributes["error.type"] = exc_type.__name__
            self.attributes["error.message"] = str(exc_val)
        else:
            self.status = "ok"
        return False

    @property
    def duration(self) -> float:
        if self.end_time is None:
            return time.perf_counter() - self.start_time
        return self.end_time - self.start_time

    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        self.events.append({
            "name": name,
            "timestamp": time.perf_counter(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent.span_id if self.parent else None,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    """HiveFlow 分布式追踪器"""

    def __init__(self, service_name: str = "hiveflow", sampling_rate: float = 1.0):
        self.service_name = service_name
        self.sampling_rate = sampling_rate
        self._current_span = None
        self._spans: list = []
        self._export_fn = None

    def set_export_fn(self, fn: Callable):
        """设置导出函数，用于将 span 发送到外部系统"""
        self._export_fn = fn

    def should_sample(self) -> bool:
        """根据采样率决定是否记录"""
        import random
        return random.random() < self.sampling_rate

    @contextmanager
    def start_as_current_span(self, name: str, attributes: Dict[str, Any] = None):
        """创建并设置当前 span"""
        if not self.should_sample():
            yield None
            return

        span = Span(name, parent=self._current_span, attributes=attributes)

        old_span = self._current_span
        self._current_span = span

        try:
            yield span
        finally:
            self._current_span = old_span
            self._spans.append(span)

            if self._export_fn:
                self._export_fn(span.to_dict())

    def trace(self, name: str, **default_attributes):
        """装饰器，自动追踪函数调用"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.start_as_current_span(name, attributes={**default_attributes}) as span:
                    if span:
                        span.set_attribute("function", func.__name__)
                        span.set_attribute("args", str(args)[:200])
                    return func(*args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.start_as_current_span(name, attributes={**default_attributes}) as span:
                    if span:
                        span.set_attribute("function", func.__name__)
                        span.set_attribute("args", str(args)[:200])
                    return await func(*args, **kwargs)

            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        return decorator

    def get_spans(self) -> list:
        """获取所有收集的 span"""
        return list(self._spans)

    def get_trace_tree(self, trace_id: str) -> list:
        """获取指定 trace 的所有 span"""
        return [s.to_dict() for s in self._spans if s.trace_id == trace_id]

    def clear_spans(self):
        """清理收集的 span"""
        self._spans.clear()


class OpenTelemetryTracer:
    """OpenTelemetry SDK 包装器 (如果安装了 opentelemetry-sdk)"""

    def __init__(self, service_name: str = "hiveflow", sampling_rate: float = 1.0):
        self.service_name = service_name
        self.sampling_rate = sampling_rate
        self._tracer = None
        self._fallback = Tracer(service_name, sampling_rate)

        # 尝试初始化 OpenTelemetry
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            resource = Resource.create({"service.name": service_name})
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)

            # 配置 OTLP 导出器
            endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

            self._tracer = trace.get_tracer(service_name)
        except ImportError:
            pass  # 使用 fallback 实现

    def start_as_current_span(self, name: str, attributes: Dict[str, Any] = None):
        """创建 span"""
        if self._tracer:
            return self._tracer.start_as_current_span(name, attributes=attributes or {})
        return self._fallback.start_as_current_span(name, attributes)

    def trace(self, name: str, **default_attributes):
        """装饰器"""
        return self._fallback.trace(name, **default_attributes)

    def get_spans(self) -> list:
        return self._fallback.get_spans()


def setup_tracing(
    service_name: str = None,
    sampling_rate: float = None,
    exporter_endpoint: str = None,
) -> OpenTelemetryTracer:
    """配置分布式追踪

    Args:
        service_name: 服务名称 (默认: OTEL_SERVICE_NAME 或 hiveflow)
        sampling_rate: 采样率 0.0-1.0 (默认: OTEL_TRACES_SAMPLER_ARG 或 1.0)
        exporter_endpoint: OTLP 导出端点 (默认: OTEL_EXPORTER_OTLP_ENDPOINT 或 http://localhost:4318)

    Returns:
        Tracer 实例
    """
    service_name = service_name or os.environ.get("OTEL_SERVICE_NAME", "hiveflow")
    sampling_rate = sampling_rate or float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0"))
    exporter_endpoint = exporter_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    return OpenTelemetryTracer(service_name, sampling_rate)


def create_span(tracer, name: str, attributes: Dict[str, Any] = None):
    """创建 span 的便捷函数"""
    return tracer.start_as_current_span(name, attributes=attributes)


def trace_workflow_execution(tracer, workflow_id: str, graph: dict):
    """追踪工作流执行的便捷函数"""
    return tracer.start_as_current_span(
        "workflow.execute",
        attributes={
            "workflow.id": workflow_id,
            "workflow.graph_nodes": len(graph),
            "workflow.graph_edges": sum(len(v.get("depends_on", [])) for v in graph.values()),
        }
    )
