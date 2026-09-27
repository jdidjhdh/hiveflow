"""HiveFlow Core - 可观测性模块

提供监控、日志和分布式追踪支持:
- Prometheus 指标导出
- 结构化日志 (JSON 格式，兼容 ELK)
- OpenTelemetry 分布式追踪
"""

from .failure_reason import (
    FailureReason,
    build_failure_payload,
    classify_exception,
    infer_failure_reason,
    normalize_failure_reason,
)
from .metrics_prometheus import PrometheusMetricsExporter, create_prometheus_registry
from .structured_logger import (
    HiveFlowLogger,
    RateLimitedLogger,
    SlidingWindowCounter,
    setup_rate_limited_logging,
    setup_structured_logging,
)
from .tracing import (
    create_span,
    get_tracer,
    get_tracing_config,
    init_tracing_if_enabled,
    is_otel_enabled,
    jaeger_search_url,
    otel_is_active,
    setup_tracing,
    trace_task_event,
    trace_workflow_execution,
)

__all__ = [
    "FailureReason",
    "HiveFlowLogger",
    "PrometheusMetricsExporter",
    "RateLimitedLogger",
    "SlidingWindowCounter",
    "build_failure_payload",
    "classify_exception",
    "create_prometheus_registry",
    "create_span",
    "get_tracer",
    "get_tracing_config",
    "infer_failure_reason",
    "init_tracing_if_enabled",
    "is_otel_enabled",
    "jaeger_search_url",
    "normalize_failure_reason",
    "otel_is_active",
    "setup_rate_limited_logging",
    "setup_structured_logging",
    "setup_tracing",
    "trace_task_event",
    "trace_workflow_execution",
]
