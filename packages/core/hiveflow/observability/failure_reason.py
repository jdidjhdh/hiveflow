"""Standard failure reason codes for execution timelines (A1/A2 observability)."""

import asyncio
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FailureReason(str, Enum):
    TOOL_ERROR = "tool_error"
    LLM_FORMAT = "llm_format"
    GUARD_BLOCK = "guard_block"
    HITL_REJECTED = "hitl_rejected"
    TIMEOUT = "timeout"
    VALIDATION = "validation_error"
    UNKNOWN = "unknown"
    # 🔧 P2 FIX: New failure categories
    RESOURCE_EXHAUSTED = "resource_exhausted"
    SERVICE_UNAVAILABLE = "service_unavailable"
    CONFIGURATION_ERROR = "configuration_error"
    
    def recommended_fix(self) -> str:
        """Return a recommended fix action for this failure reason."""
        fixes = {
            FailureReason.TOOL_ERROR: "Check tool configuration and input parameters",
            FailureReason.LLM_FORMAT: "Validate LLM response format and add retry logic",
            FailureReason.GUARD_BLOCK: "Review guard rules and adjust constraints",
            FailureReason.HITL_REJECTED: "Check human feedback and adjust task parameters",
            FailureReason.TIMEOUT: "Increase timeout or optimize operation",
            FailureReason.VALIDATION: "Review validation schema and input data",
            FailureReason.UNKNOWN: "Check logs for detailed error information",
            FailureReason.RESOURCE_EXHAUSTED: "Reduce load or increase capacity limits",
            FailureReason.SERVICE_UNAVAILABLE: "Check service health and circuit breaker state",
            FailureReason.CONFIGURATION_ERROR: "Fix duplicate registrations or configuration conflicts",
        }
        return fixes.get(self, "Check logs for detailed error information")


@dataclass
class ClassifiedFailure:
    """Classification result with recommended fix action."""
    reason: FailureReason
    error_message: str
    exception_type: str
    recommended_fix: str


def normalize_failure_reason(value: Any) -> FailureReason:
    """Coerce arbitrary values to a known FailureReason."""
    if isinstance(value, FailureReason):
        return value
    if value is None:
        return FailureReason.UNKNOWN
    text = str(value).strip().lower()
    for reason in FailureReason:
        if text == reason.value:
            return reason
    return FailureReason.UNKNOWN


def build_failure_payload(
    reason: FailureReason | str,
    *,
    error: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Standard payload fragment for failed/timeout bus events."""
    normalized = normalize_failure_reason(reason)
    payload: dict[str, Any] = {
        "failure_reason": normalized.value,
        "error": error or normalized.value,
    }
    payload.update(extra)
    return payload


def payload_failure_reason(payload: dict[str, Any] | None) -> FailureReason | None:
    """Read explicit failure_reason from a payload if present."""
    if not payload:
        return None
    raw = payload.get("failure_reason")
    if raw is None:
        return None
    reason = normalize_failure_reason(raw)
    return reason if reason != FailureReason.UNKNOWN or raw == FailureReason.UNKNOWN.value else None


def classify_exception(exc: BaseException) -> FailureReason:
    """
    Map an exception to a standard failure reason.
    
    🔧 Enhanced classification (DX improvement):
    - QueueFullError → RESOURCE_EXHAUSTED
    - CircuitBreakerOpenError → SERVICE_UNAVAILABLE  
    - ToolNameConflictError → CONFIGURATION_ERROR
    
    Args:
        exc: Exception to classify
        
    Returns:
        FailureReason enum value
    """
    from .. import AbortExecutionException
    
    # Check for explicit failure_reason in AbortExecutionException
    if isinstance(exc, AbortExecutionException):
        explicit = getattr(exc, "failure_reason", None)
        if explicit:
            return normalize_failure_reason(explicit)

    # 🔧 New exception type classification
    exc_name = type(exc).__name__
    
    # QueueFullError → resource_exhausted
    if exc_name == "QueueFullError":
        return FailureReason.RESOURCE_EXHAUSTED
    
    # CircuitBreakerOpenError → service_unavailable
    if exc_name == "CircuitBreakerOpenError":
        return FailureReason.SERVICE_UNAVAILABLE
    
    # ToolNameConflictError → configuration_error
    if exc_name == "ToolNameConflictError":
        return FailureReason.CONFIGURATION_ERROR
    
    # Standard timeout classification
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return FailureReason.TIMEOUT

    if isinstance(exc, json.JSONDecodeError):
        return FailureReason.LLM_FORMAT

    # Message-based classification
    msg = str(exc).lower()
    
    # 🔧 Additional patterns for new categories
    if any(k in msg for k in ("queue full", "rate limit", "memory limit", "capacity", "exhausted")):
        return FailureReason.RESOURCE_EXHAUSTED
    
    if any(k in msg for k in ("circuit breaker", "service unavailable", "connection refused", "temporarily unavailable")):
        return FailureReason.SERVICE_UNAVAILABLE
    
    if any(k in msg for k in ("conflict", "duplicate", "already registered", "configuration", "misconfigured")):
        return FailureReason.CONFIGURATION_ERROR
    
    # Original patterns
    if "hitl" in msg and ("reject" in msg or "cancel" in msg):
        return FailureReason.HITL_REJECTED
    if "timed out" in msg or "timeout" in msg or "time out" in msg:
        return FailureReason.TIMEOUT
    if "guard" in msg:
        return FailureReason.GUARD_BLOCK
    if any(k in msg for k in ("validation", "expectation")):
        return FailureReason.VALIDATION
    if any(k in msg for k in ("json", "parse", "format", "schema", "invalid response")):
        return FailureReason.LLM_FORMAT
    if any(k in msg for k in ("tool", "mcp")) or "tool" in exc_name:
        return FailureReason.TOOL_ERROR

    return FailureReason.UNKNOWN


def classify_exception_with_fix(exc: BaseException) -> ClassifiedFailure:
    """
    Classify an exception and provide recommended fix action.
    
    Args:
        exc: Exception to classify
        
    Returns:
        ClassifiedFailure with reason, message, type, and recommended fix
    """
    reason = classify_exception(exc)
    return ClassifiedFailure(
        reason=reason,
        error_message=str(exc),
        exception_type=type(exc).__name__,
        recommended_fix=reason.recommended_fix(),
    )


def infer_failure_reason(
    *,
    status: str = "",
    intent: str = "",
    payload: dict[str, Any] | None = None,
    hitl_status: str = "",
) -> FailureReason:
    """Resolve failure reason; prefers explicit payload.failure_reason (A2)."""
    payload = payload or {}
    explicit = payload_failure_reason(payload)
    if explicit is not None:
        return explicit

    text = " ".join(
        str(v)
        for v in (
            payload.get("error"),
            payload.get("message"),
            payload.get("detail"),
            payload.get("reason"),
        )
        if v
    ).lower()
    intent_l = (intent or "").lower()
    status_l = (status or "").lower()
    hitl_l = (hitl_status or "").lower()

    if status_l == "timeout" or intent_l == "intent.timeout":
        return FailureReason.TIMEOUT
    if hitl_l in ("rejected", "cancelled") or ("hitl" in intent_l and hitl_l == "rejected"):
        return FailureReason.HITL_REJECTED
    if hitl_l == "timed_out":
        return FailureReason.TIMEOUT
    if "guard" in text or "guard" in intent_l or payload.get("guard"):
        return FailureReason.GUARD_BLOCK
    if any(k in text for k in ("json", "parse", "format", "schema", "invalid response")):
        return FailureReason.LLM_FORMAT
    if any(k in text for k in ("validation", "expectation")):
        return FailureReason.VALIDATION
    if status_l == "failed" or intent_l == "task.failed":
        if payload.get("tool") or "tool" in text or "mcp" in text:
            return FailureReason.TOOL_ERROR
        return FailureReason.TOOL_ERROR if text else FailureReason.UNKNOWN
    return FailureReason.UNKNOWN
