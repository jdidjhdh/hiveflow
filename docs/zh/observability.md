# 可观测性

HiveFlow 暴露指标、审计日志，以及可选的 OpenTelemetry 追踪。

## Studio 分析

启用**真实模式**后，Analytics 仪表盘读取：

- `GET /api/analytics/prometheus` — 聚合的 Prometheus 风格指标
- 工作流执行中的节点耗时统计（`record_node_execution`）

## Core 指标

```python
from hiveflow import MetricsCollector

collector = MetricsCollector()
collector.record_counter("intents_scheduled", 1)
```

## OpenTelemetry（可选）

安装 SDK extra 并配置 tracer：

```bash
pip install opentelemetry-api opentelemetry-sdk
```

```python
from hiveflow.observability.tracing import create_tracer

tracer = create_tracer("my-service", sampling_rate=1.0)
with tracer.start_span("orchestrate") as span:
    span.set_attribute("intent_id", "task-1")
```

若未安装 OpenTelemetry，HiveFlow 会回退到轻量级进程内 span 实现。

## Studio 中的追踪

- **Tracer** 页面 — 实时事件流
- **Replay**（`/replay`）— 按 `intent_id` / `trace_id` 索引的审计历史

## 生产环境

Prometheus 抓取端点与 Docker Compose 示例请参阅 [部署](deployment.md)。
