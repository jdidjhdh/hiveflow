"""HiveFlow Core - OpenTelemetry 分布式追踪

一键开启（A3）::

    export HIVEFLOW_OTEL_ENABLED=1
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
    export OTEL_SERVICE_NAME=hiveflow-studio
    export HIVEFLOW_JAEGER_UI_URL=http://localhost:16686

依赖::

    pip install hiveflow-core[otel]
    # 或 opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
"""

from __future__ import annotations

import functools
import logging
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

_global_tracer: OpenTelemetryTracer | None = None
_otel_sdk_active = False


def is_otel_enabled() -> bool:
    """True when HIVEFLOW_OTEL_ENABLED=1|true|yes."""
    return os.environ.get("HIVEFLOW_OTEL_ENABLED", "").strip().lower() in ("1", "true", "yes")


def otel_is_active() -> bool:
    """True when enabled and OTLP SDK initialized successfully."""
    return _otel_sdk_active


def get_tracing_config() -> dict[str, Any]:
    """Runtime tracing config for Studio / ops."""
    service = os.environ.get("OTEL_SERVICE_NAME", "hiveflow")
    return {
        "enabled": is_otel_enabled(),
        "active": otel_is_active(),
        "service_name": service,
        "otlp_endpoint": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        "jaeger_ui_url": os.environ.get("HIVEFLOW_JAEGER_UI_URL", "http://localhost:16686"),
        "tempo_url": os.environ.get("HIVEFLOW_TEMPO_URL", ""),
        "sampling_rate": float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0")),
    }


def jaeger_search_url(intent_id: str, *, service_name: str | None = None, jaeger_ui: str | None = None) -> str:
    """Build Jaeger UI search URL for an intent/workflow id."""
    cfg = get_tracing_config()
    base = (jaeger_ui or cfg["jaeger_ui_url"]).rstrip("/")
    svc = service_name or cfg["service_name"]
    tags = {"intent.id": intent_id}
    import json
    from urllib.parse import quote

    return f"{base}/search?service={quote(svc)}&tags={quote(json.dumps(tags))}"


def _normalize_otlp_endpoint(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/v1/traces"):
        return endpoint
    return endpoint


class Span:
    """简化的 Span 实现 (不依赖 OpenTelemetry SDK)"""

    def __init__(self, name: str, parent: Span | None = None, attributes: dict[str, Any] | None = None):
        self.name = name
        self.parent = parent
        self.attributes = attributes or {}
        self.start_time = time.perf_counter()
        self.end_time = None
        self.status = "unset"
        self.events: list[dict[str, Any]] = []

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

    def add_event(self, name: str, attributes: dict[str, Any] | None = None):
        self.events.append(
            {
                "name": name,
                "timestamp": time.perf_counter(),
                "attributes": attributes or {},
            }
        )

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def to_dict(self) -> dict[str, Any]:
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
    """HiveFlow 进程内追踪器（OTel 未启用或未安装时的 fallback）"""

    def __init__(self, service_name: str = "hiveflow", sampling_rate: float = 1.0):
        self.service_name = service_name
        self.sampling_rate = sampling_rate
        self._current_span: Span | None = None
        self._spans: list[Span] = []
        self._export_fn: Callable | None = None
        self.otel_available = False

    def set_export_fn(self, fn: Callable):
        self._export_fn = fn

    def should_sample(self) -> bool:
        import random

        return random.random() < self.sampling_rate

    @contextmanager
    def start_as_current_span(self, name: str, attributes: dict[str, Any] | None = None) -> Iterator[Span | None]:
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
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.start_as_current_span(name, attributes={**default_attributes}) as span:
                    if span:
                        span.set_attribute("function", func.__name__)
                    return func(*args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.start_as_current_span(name, attributes={**default_attributes}) as span:
                    if span:
                        span.set_attribute("function", func.__name__)
                    return await func(*args, **kwargs)

            import asyncio

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def get_spans(self) -> list:
        return list(self._spans)

    def get_trace_tree(self, trace_id: str) -> list:
        return [s.to_dict() for s in self._spans if s.trace_id == trace_id]

    def clear_spans(self):
        self._spans.clear()


class OpenTelemetryTracer:
    """OpenTelemetry SDK 包装器；未启用或未安装时回退到 Tracer。"""

    def __init__(
        self,
        service_name: str = "hiveflow",
        sampling_rate: float = 1.0,
        exporter_endpoint: str | None = None,
    ):
        self.service_name = service_name
        self.sampling_rate = sampling_rate
        self.exporter_endpoint = _normalize_otlp_endpoint(
            exporter_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        )
        self._fallback = Tracer(service_name, sampling_rate)
        self._otel_tracer = None
        self.otel_available = False

    def _init_otel_sdk(self) -> bool:
        global _otel_sdk_active
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)

            exporter = OTLPSpanExporter(endpoint=self.exporter_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            self._otel_tracer = trace.get_tracer(self.service_name)
            self.otel_available = True
            self._fallback.otel_available = True
            _otel_sdk_active = True
            logger.info(
                "OpenTelemetry tracing active: service=%s endpoint=%s",
                self.service_name,
                self.exporter_endpoint,
            )
            return True
        except ImportError:
            logger.warning(
                "HIVEFLOW_OTEL_ENABLED=1 but OpenTelemetry packages missing. Install: pip install hiveflow-core[otel]"
            )
            return False
        except Exception:
            logger.exception("Failed to initialize OpenTelemetry tracing")
            return False

    @contextmanager
    def start_as_current_span(self, name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
        attrs = attributes or {}
        if self._otel_tracer:
            from opentelemetry.trace import Status, StatusCode

            with self._otel_tracer.start_as_current_span(name) as span:
                for key, val in attrs.items():
                    span.set_attribute(key, val)
                try:
                    yield span
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
            return

        with self._fallback.start_as_current_span(name, attributes=attrs) as span:
            yield span

    def trace(self, name: str, **default_attributes):
        return self._fallback.trace(name, **default_attributes)

    def get_spans(self) -> list:
        return self._fallback.get_spans()

    def get_trace_tree(self, trace_id: str) -> list:
        """Return in-process fallback spans for a trace id (Studio /api/monitoring/traces)."""
        return self._fallback.get_trace_tree(trace_id)

    def clear_spans(self) -> None:
        self._fallback.clear_spans()


def setup_tracing(
    service_name: str | None = None,
    sampling_rate: float | None = None,
    exporter_endpoint: str | None = None,
) -> OpenTelemetryTracer:
    """配置分布式追踪。仅当 HIVEFLOW_OTEL_ENABLED=1 时连接 OTLP 导出器。"""
    service_name = service_name or os.environ.get("OTEL_SERVICE_NAME", "hiveflow")
    sampling_rate = (
        sampling_rate if sampling_rate is not None else float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0"))
    )
    exporter_endpoint = exporter_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    tracer = OpenTelemetryTracer(service_name, sampling_rate, exporter_endpoint)
    if is_otel_enabled():
        tracer._init_otel_sdk()
    return tracer


def init_tracing_if_enabled(service_name: str | None = None) -> OpenTelemetryTracer:
    """Idempotent init for application startup."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = setup_tracing(service_name=service_name)
    return _global_tracer


def get_tracer() -> OpenTelemetryTracer:
    """Return global tracer, initializing fallback if needed."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = setup_tracing()
    return _global_tracer


def create_span(tracer: OpenTelemetryTracer, name: str, attributes: dict[str, Any] | None = None):
    return tracer.start_as_current_span(name, attributes=attributes)


def trace_workflow_execution(tracer: OpenTelemetryTracer, workflow_id: str, graph: dict):
    return tracer.start_as_current_span(
        "workflow.execute",
        attributes={
            "workflow.id": workflow_id,
            "intent.id": workflow_id,
            "workflow.graph_nodes": len(graph),
            "workflow.graph_edges": sum(len(v.get("depends_on", [])) for v in graph.values()),
        },
    )


def trace_task_event(
    tracer: OpenTelemetryTracer,
    topic: str,
    *,
    intent_id: str,
    emitter: str = "",
    failure_reason: str = "",
    extra: dict[str, Any] | None = None,
):
    """Short-lived span for bus events (task.completed / task.failed / intent.timeout)."""
    attrs: dict[str, Any] = {
        "intent.id": intent_id,
        "event.topic": topic,
        "emitter": emitter,
    }
    if failure_reason:
        attrs["failure.reason"] = failure_reason
    if extra:
        attrs.update(extra)
    name = topic.replace(".", "/")
    return tracer.start_as_current_span(name, attributes=attrs)
