"""Tests for A3 OpenTelemetry one-click tracing."""
import os

import pytest


def test_is_otel_disabled_by_default(monkeypatch):
    monkeypatch.delenv("HIVEFLOW_OTEL_ENABLED", raising=False)
    from hiveflow.observability.tracing import is_otel_enabled

    assert is_otel_enabled() is False


def test_is_otel_enabled_flag(monkeypatch):
    monkeypatch.setenv("HIVEFLOW_OTEL_ENABLED", "1")
    from hiveflow.observability.tracing import is_otel_enabled

    assert is_otel_enabled() is True


def test_jaeger_search_url(monkeypatch):
    monkeypatch.setenv("HIVEFLOW_JAEGER_UI_URL", "http://localhost:16686")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "hiveflow-studio")
    from hiveflow.observability.tracing import jaeger_search_url

    url = jaeger_search_url("intent-abc")
    assert "16686" in url
    assert "intent-abc" in url
    assert "hiveflow-studio" in url


def test_fallback_spans_when_otel_off(monkeypatch):
    monkeypatch.delenv("HIVEFLOW_OTEL_ENABLED", raising=False)
    from hiveflow.observability import tracing as tracing_mod

    tracing_mod._global_tracer = None
    tracing_mod._otel_sdk_active = False
    tracer = tracing_mod.get_tracer()
    with tracer.start_as_current_span("test.span", attributes={"intent.id": "x"}):
        pass
    assert tracing_mod.otel_is_active() is False
    spans = tracer.get_spans()
    assert len(spans) >= 1
    trace_id = spans[0].trace_id if hasattr(spans[0], "trace_id") else spans[0]["trace_id"]
    tree = tracer.get_trace_tree(trace_id)
    assert len(tree) >= 1


@pytest.mark.skipif(
    os.environ.get("HIVEFLOW_TEST_OTEL") != "1",
    reason="Set HIVEFLOW_TEST_OTEL=1 with otel packages installed",
)
def test_otel_sdk_init_when_enabled(monkeypatch):
    monkeypatch.setenv("HIVEFLOW_OTEL_ENABLED", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    from hiveflow.observability import tracing as tracing_mod

    tracing_mod._global_tracer = None
    tracing_mod._otel_sdk_active = False
    tracer = tracing_mod.init_tracing_if_enabled("test-service")
    assert tracer.otel_available is True
