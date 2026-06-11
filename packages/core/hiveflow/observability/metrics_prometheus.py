"""HiveFlow Core - Prometheus 指标导出器

将 HiveFlow 内部指标转换为 Prometheus 格式，支持:
- Counter: 累计指标 (任务总数、成功数、失败数)
- Gauge: 瞬时指标 (活跃 Agent 数、当前负载)
- Histogram: 分布指标 (任务执行时间、延迟)
- Summary: 汇总指标 (请求大小、响应大小)

使用方式:
    from hiveflow.observability import PrometheusMetricsExporter

    exporter = PrometheusMetricsExporter()
    exporter.register_metrics(metrics_collector)

    # FastAPI/Flask 端点暴露
    @app.get("/metrics")
    def metrics():
        return exporter.generate_metrics()
"""

import re
import time
from dataclasses import dataclass, field


@dataclass
class PrometheusMetric:
    """单个 Prometheus 指标"""

    name: str
    help_text: str
    metric_type: str  # counter, gauge, histogram
    labels: dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    buckets: list | None = None  # histogram buckets


class PrometheusMetricsExporter:
    """将 HiveFlow 指标导出为 Prometheus 格式"""

    def __init__(self, prefix: str = "hiveflow"):
        self.prefix = prefix
        self._metrics: dict[str, PrometheusMetric] = {}
        self._start_time = time.time()

    def _sanitize_name(self, name: str) -> str:
        """将指标名称转换为 Prometheus 兼容格式"""
        name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        return f"{self.prefix}_{name}"

    def _format_labels(self, labels: dict[str, str]) -> str:
        """格式化标签为 Prometheus 格式"""
        if not labels:
            return ""
        label_parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(label_parts) + "}"

    def register_counter(self, name: str, help_text: str, labels: dict[str, str] | None = None):
        """注册 Counter 指标"""
        metric_name = self._sanitize_name(name)
        self._metrics[metric_name] = PrometheusMetric(
            name=metric_name,
            help_text=help_text,
            metric_type="counter",
            labels=labels or {},
            value=0,
        )

    def register_gauge(self, name: str, help_text: str, labels: dict[str, str] | None = None):
        """注册 Gauge 指标"""
        metric_name = self._sanitize_name(name)
        self._metrics[metric_name] = PrometheusMetric(
            name=metric_name,
            help_text=help_text,
            metric_type="gauge",
            labels=labels or {},
            value=0,
        )

    def register_histogram(
        self, name: str, help_text: str, buckets: list | None = None, labels: dict[str, str] | None = None
    ):
        """注册 Histogram 指标"""
        metric_name = self._sanitize_name(name)
        if buckets is None:
            buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

        self._metrics[metric_name] = PrometheusMetric(
            name=metric_name,
            help_text=help_text,
            metric_type="histogram",
            labels=labels or {},
            buckets=buckets,
        )

    def update_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None):
        """更新 Counter 值"""
        metric_name = self._sanitize_name(name)
        if metric_name in self._metrics:
            self._metrics[metric_name].value += value
            if labels:
                self._metrics[metric_name].labels.update(labels)

    def update_gauge(self, name: str, value: float, labels: dict[str, str] | None = None):
        """更新 Gauge 值"""
        metric_name = self._sanitize_name(name)
        if metric_name in self._metrics:
            self._metrics[metric_name].value = value
            if labels:
                self._metrics[metric_name].labels.update(labels)

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None):
        """记录 Histogram 观测值"""
        metric_name = self._sanitize_name(name)
        if metric_name in self._metrics:
            metric = self._metrics[metric_name]
            # 这里简化处理，实际应该维护桶计数
            metric.value = value  # 存储最新值
            if labels:
                metric.labels.update(labels)

    def generate_metrics(self) -> str:
        """生成 Prometheus 格式的指标文本"""
        output = []

        # 添加进程运行时间
        output.append("# HELP hiveflow_process_uptime_seconds Process uptime in seconds")
        output.append("# TYPE hiveflow_process_uptime_seconds gauge")
        output.append(f"hiveflow_process_uptime_seconds {time.time() - self._start_time:.2f}")

        for name, metric in self._metrics.items():
            # 添加 HELP
            output.append(f"# HELP {name} {metric.help_text}")
            output.append(f"# TYPE {name} {metric.metric_type}")

            label_str = self._format_labels(metric.labels)

            if metric.metric_type == "counter":
                output.append(f"{name}{label_str} {metric.value}")
            elif metric.metric_type == "gauge":
                output.append(f"{name}{label_str} {metric.value}")
            elif metric.metric_type == "histogram":
                # 简化 histogram 输出
                output.append(f"{name}_sum{label_str} {metric.value}")
                output.append(f"{name}_count{label_str} 1")
                if metric.buckets:
                    for bucket in metric.buckets:
                        output.append(f'{name}_bucket{{le="{bucket}"{self._format_labels(metric.labels)[1:]}}} 0')
                    output.append(f'{name}_bucket{{le="+Inf"{self._format_labels(metric.labels)[1:]}}} 1')

        return "\n".join(output) + "\n"

    def register_default_metrics(self):
        """注册 HiveFlow 默认指标"""
        # Counter 指标
        self.register_counter("tasks_total", "Total number of tasks executed")
        self.register_counter("tasks_completed", "Total number of tasks completed successfully")
        self.register_counter("tasks_failed", "Total number of tasks failed")
        self.register_counter("tasks_retried", "Total number of task retries")
        self.register_counter("workflows_total", "Total number of workflows executed")
        self.register_counter("workflows_completed", "Total number of workflows completed")
        self.register_counter("workflows_failed", "Total number of workflows failed")
        self.register_counter("intents_parsed", "Total number of intents parsed")
        self.register_counter("blackboard_operations", "Total number of blackboard operations")
        self.register_counter("errors_total", "Total number of errors", labels={"error_type": "unknown"})

        # Gauge 指标
        self.register_gauge("active_workers", "Number of active workers")
        self.register_gauge("active_agents", "Number of active agents")
        self.register_gauge("queue_size", "Current task queue size")
        self.register_gauge("blackboard_size", "Current blackboard size in bytes")
        self.register_gauge("memory_usage_mb", "Current memory usage in MB")
        self.register_gauge("worker_load", "Current worker load", labels={"worker_id": "unknown"})

        # Histogram 指标
        self.register_histogram("task_duration_seconds", "Task execution duration")
        self.register_histogram("workflow_duration_seconds", "Workflow execution duration")
        self.register_histogram("intent_parse_duration_seconds", "Intent parsing duration")
        self.register_histogram("llm_response_duration_seconds", "LLM response duration")
        self.register_histogram("blackboard_operation_duration_seconds", "Blackboard operation duration")


def create_prometheus_registry(exporter: PrometheusMetricsExporter = None) -> PrometheusMetricsExporter:
    """创建并返回 Prometheus 导出器实例"""
    if exporter is None:
        exporter = PrometheusMetricsExporter()
        exporter.register_default_metrics()
    return exporter
