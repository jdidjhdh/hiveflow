# Observability

HiveFlow exposes metrics, audit logs, and optional OpenTelemetry tracing.

## Studio Analytics

With **real mode** enabled, the Analytics dashboard reads:

- `GET /api/analytics/prometheus` — aggregated Prometheus-style metrics
- Node duration stats from workflow execution (`record_node_execution`)

## Core metrics

```python
from hiveflow import MetricsCollector

collector = MetricsCollector()
collector.record_counter("intents_scheduled", 1)
```

## OpenTelemetry (optional)

Install the SDK extras and configure a tracer:

```bash
pip install opentelemetry-api opentelemetry-sdk
```

```python
from hiveflow.observability.tracing import create_tracer

tracer = create_tracer("my-service", sampling_rate=1.0)
with tracer.start_span("orchestrate") as span:
    span.set_attribute("intent_id", "task-1")
```

If OpenTelemetry is not installed, HiveFlow falls back to a lightweight in-process span implementation.

## Tracing in Studio

- **Tracer** page — live event stream
- **Replay** (`/replay`) — audit history keyed by `intent_id` / `trace_id`

## Production

See [Deployment](deployment.md) for Prometheus scrape endpoints and Docker Compose examples.
