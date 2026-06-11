"""Tests for hiveflow.observability module."""
from hiveflow.observability import (
    PrometheusMetricsExporter,
    create_prometheus_registry,
    setup_structured_logging,
)
from hiveflow.observability.tracing import Tracer


def test_prometheus_exporter_register_and_generate():
    exporter = PrometheusMetricsExporter(prefix="hiveflow_test")
    exporter.register_counter("tasks_total", "Total tasks")
    exporter.update_counter("tasks_total", 3)
    output = exporter.generate_metrics()
    assert "hiveflow_test_tasks_total" in output
    assert "3" in output


def test_create_prometheus_registry():
    registry = create_prometheus_registry()
    assert isinstance(registry, PrometheusMetricsExporter)


def test_structured_logger_and_tracer_span():
    logger = setup_structured_logging(level="INFO", service="test-hiveflow")
    logger.info("hello", workflow_id="wf-1")

    tracer = Tracer("test-service")
    with tracer.start_as_current_span("test.operation", attributes={"node": "n1"}) as span:
        assert span.name == "test.operation"
        assert span.attributes["node"] == "n1"

    spans = tracer.get_spans()
    assert len(spans) == 1
