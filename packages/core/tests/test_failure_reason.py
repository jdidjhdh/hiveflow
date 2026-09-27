"""Tests for standard failure_reason classification (A2)."""
import json

import pytest

from hiveflow import AbortExecutionException
from hiveflow.observability.failure_reason import (
    FailureReason,
    build_failure_payload,
    classify_exception,
    infer_failure_reason,
    normalize_failure_reason,
)


def test_normalize_failure_reason():
    assert normalize_failure_reason("tool_error") == FailureReason.TOOL_ERROR
    assert normalize_failure_reason(FailureReason.GUARD_BLOCK) == FailureReason.GUARD_BLOCK
    assert normalize_failure_reason("not_a_reason") == FailureReason.UNKNOWN


def test_build_failure_payload():
    payload = build_failure_payload(FailureReason.TIMEOUT, error="deadline exceeded")
    assert payload["failure_reason"] == "timeout"
    assert payload["error"] == "deadline exceeded"


def test_classify_abort_with_explicit_reason():
    exc = AbortExecutionException("blocked", failure_reason=FailureReason.GUARD_BLOCK.value)
    assert classify_exception(exc) == FailureReason.GUARD_BLOCK


def test_classify_json_decode_error():
    assert classify_exception(json.JSONDecodeError("bad", "doc", 0)) == FailureReason.LLM_FORMAT


def test_classify_timeout():
    assert classify_exception(TimeoutError("timed out")) == FailureReason.TIMEOUT


def test_infer_prefers_explicit_payload():
    reason = infer_failure_reason(
        status="failed",
        payload={"failure_reason": "hitl_rejected", "error": "user said no"},
    )
    assert reason == FailureReason.HITL_REJECTED


def test_infer_guard_from_message():
    reason = infer_failure_reason(
        status="failed",
        payload={"error": "Input guard blocked dependency"},
    )
    assert reason == FailureReason.GUARD_BLOCK
