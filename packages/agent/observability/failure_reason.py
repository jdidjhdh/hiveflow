"""
🔧 OBSERVABILITY: Failure Reason Classification

Provides structured failure classification for Agent orchestration errors.
Used by cognitive.py to categorize failures into:
- LLM_UNAVAILABLE: API timeout, rate limit, connection error
- TOOL_MISSING: Required skill/tool not found
- PLAN_LOGIC_ERROR: Invalid TaskGraph, cyclic dependency, missing final_answer
- TIMEOUT: Global orchestration timeout exceeded
- HITL_REJECTED: Human-in-the-loop gate rejected
- RESOURCE_EXHAUSTED: Memory/CPU limits hit

Usage:
    from observability.failure_reason import FailureReason, classify_exception
    
    try:
        result = await orchestrate(...)
    except Exception as e:
        reason = classify_exception(e)
        logger.error(f"[trace_id={trace_id}] Failure: {reason.value}")
"""
import asyncio
import json
from enum import Enum


class FailureReason(str, Enum):
    """Structured failure reason codes for Agent orchestration."""
    
    # LLM-related failures
    LLM_UNAVAILABLE = "llm_unavailable"       # API timeout, rate limit, connection error
    LLM_RATE_LIMIT = "llm_rate_limit"         # 429 Too Many Requests
    LLM_TIMEOUT = "llm_timeout"               # Response timeout
    LLM_INVALID_RESPONSE = "llm_invalid_response"  # Malformed JSON, hallucinated tool
    
    # Tool-related failures
    TOOL_MISSING = "tool_missing"             # Required skill not in skill_bindings
    TOOL_ERROR = "tool_error"                 # Tool execution raised exception
    TOOL_TIMEOUT = "tool_timeout"             # Tool execution timeout
    
    # Plan-related failures
    PLAN_LOGIC_ERROR = "plan_logic_error"     # Invalid TaskGraph structure
    CYCLIC_DEPENDENCY = "cyclic_dependency"   # Circular dependency detected
    MISSING_FINAL_ANSWER = "missing_final_answer"  # No final_answer node
    
    # Orchestration failures
    TIMEOUT = "timeout"                       # Global orchestration timeout
    SCHEDULE_FAILURE = "schedule_failure"     # Scheduler could not assign worker
    UPSTREAM_FAILURE = "upstream_failure"     # Dependency node failed
    
    # HITL failures
    HITL_REJECTED = "hitl_rejected"           # Human rejected gate
    HITL_TIMEOUT = "hitl_timeout"             # No human response within timeout
    
    # Resource failures
    RESOURCE_EXHAUSTED = "resource_exhausted" # Memory/CPU limits
    BLACKBOARD_ERROR = "blackboard_error"     # Blackboard read/write failure
    
    # Unknown
    UNKNOWN = "unknown"                       # Uncategorized error


def classify_exception(exception: Exception, context: dict | None = None) -> FailureReason:
    """
    🔧 OBSERVABILITY: Classify exception into structured FailureReason.
    
    Args:
        exception: The caught exception
        context: Optional context dict (e.g., {"skill_name": "web_search"})
    
    Returns:
        FailureReason enum value
    
    Examples:
        classify_exception(ValueError("Unknown skill 'foo'"))
        -> FailureReason.TOOL_MISSING
        
        classify_exception(asyncio.TimeoutError())
        -> FailureReason.TIMEOUT
        
        classify_exception(json.JSONDecodeError())
        -> FailureReason.LLM_INVALID_RESPONSE
    """
    ctx = context or {}
    
    # 1. Check exception type
    exc_type = type(exception).__name__
    exc_message = str(exception).lower()
    
    # 2. LLM-related failures
    if isinstance(exception, asyncio.TimeoutError):
        # Check if it's LLM timeout or general timeout
        if "llm" in exc_message or "stream" in exc_message:
            return FailureReason.LLM_TIMEOUT
        return FailureReason.TIMEOUT
    
    if isinstance(exception, json.JSONDecodeError):
        return FailureReason.LLM_INVALID_RESPONSE
    
    # Check for rate limit in message (common pattern)
    if "rate limit" in exc_message or "429" in exc_message:
        return FailureReason.LLM_RATE_LIMIT
    
    if "connection" in exc_message or "unavailable" in exc_message:
        return FailureReason.LLM_UNAVAILABLE
    
    # 3. Tool-related failures
    if "unknown skill" in exc_message or "tool not found" in exc_message:
        return FailureReason.TOOL_MISSING
    
    if "tool error" in exc_message or "tool failed" in exc_message:
        return FailureReason.TOOL_ERROR
    
    # Check context for skill-specific errors
    if "skill_name" in ctx:
        skill = ctx["skill_name"]
        if f"'{skill}'" in exc_message:
            return FailureReason.TOOL_MISSING
    
    # 4. Plan-related failures
    if "cyclic" in exc_message or "circular dependency" in exc_message:
        return FailureReason.CYCLIC_DEPENDENCY
    
    if "final_answer" in exc_message or "missing final" in exc_message:
        return FailureReason.MISSING_FINAL_ANSWER
    
    if "invalid taskgraph" in exc_message or "invalid graph" in exc_message:
        return FailureReason.PLAN_LOGIC_ERROR
    
    # 5. Orchestration failures
    if "schedule" in exc_message or "no worker" in exc_message:
        return FailureReason.SCHEDULE_FAILURE
    
    if "upstream" in exc_message or "dependency failed" in exc_message:
        return FailureReason.UPSTREAM_FAILURE
    
    # 6. HITL failures
    if "hitl" in exc_message or "gate" in exc_message:
        if "rejected" in exc_message:
            return FailureReason.HITL_REJECTED
        if "timeout" in exc_message:
            return FailureReason.HITL_TIMEOUT
    
    # 7. Resource failures
    if "memory" in exc_message or "oom" in exc_message:
        return FailureReason.RESOURCE_EXHAUSTED
    
    if "blackboard" in exc_message or "key not found" in exc_message:
        return FailureReason.BLACKBOARD_ERROR
    
    # 8. Specific exception types
    if exc_type == "AbortExecutionException":
        # Parse the message for specific reason
        if "upstream" in exc_message:
            return FailureReason.UPSTREAM_FAILURE
        if "missing" in exc_message:
            return FailureReason.MISSING_FINAL_ANSWER
        return FailureReason.PLAN_LOGIC_ERROR
    
    if exc_type == "ValueError":
        if "skill" in exc_message or "tool" in exc_message:
            return FailureReason.TOOL_MISSING
        return FailureReason.PLAN_LOGIC_ERROR
    
    # Default: unknown
    return FailureReason.UNKNOWN


def infer_failure_reason(status: str, error_message: str | None = None, 
                         payload: dict | None = None) -> FailureReason:
    """
    Infer failure reason from orchestration result status.
    
    Args:
        status: Orchestration status ("failed", "timeout", "rejected")
        error_message: Optional error message string
        payload: Optional payload dict with additional context
    
    Returns:
        FailureReason enum value
    """
    if status == "timeout":
        return FailureReason.TIMEOUT
    
    if status == "rejected":
        return FailureReason.HITL_REJECTED
    
    if status == "failed":
        if error_message:
            # Try to classify from error message
            msg_lower = error_message.lower()
            if "llm" in msg_lower or "api" in msg_lower:
                return FailureReason.LLM_UNAVAILABLE
            if "tool" in msg_lower or "skill" in msg_lower:
                return FailureReason.TOOL_ERROR
            if "schedule" in msg_lower:
                return FailureReason.SCHEDULE_FAILURE
        
        # Check payload for explicit failure_reason
        if payload and "failure_reason" in payload:
            return FailureReason(payload["failure_reason"])
    
    return FailureReason.UNKNOWN