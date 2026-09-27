"""HiveFlow Core - 全局指标实例

提供单例 PrometheusMetricsExporter 实例，供 Core 模块使用。

使用方式:
    from hiveflow.observability.metrics import metrics
    
    metrics.update_counter("tasks_total")
    metrics.observe_histogram("task_duration_seconds", 0.5)
"""

import os

from .metrics_prometheus import PrometheusMetricsExporter, create_prometheus_registry

# 全局单例指标导出器
_metrics_instance: PrometheusMetricsExporter | None = None


def get_metrics() -> PrometheusMetricsExporter:
    """获取全局指标实例"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = create_prometheus_registry()
    return _metrics_instance


def reset_metrics() -> None:
    """重置指标实例（用于测试）"""
    global _metrics_instance
    _metrics_instance = None


# 导出全局实例
metrics = get_metrics()


def setup_metrics(prefix: str = "hiveflow") -> PrometheusMetricsExporter:
    """
    配置并返回全局指标导出器。
    
    Args:
        prefix: 指标名称前缀
        
    Returns:
        PrometheusMetricsExporter 实例
    """
    global _metrics_instance
    _metrics_instance = PrometheusMetricsExporter(prefix=prefix)
    _metrics_instance.register_default_metrics()
    return _metrics_instance