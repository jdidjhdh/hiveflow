"""HiveFlow Exception Hierarchy

This module defines the base exception classes for HiveFlow with actionable fix hints.
All custom exceptions inherit from HiveFlowError and provide default fix_hint messages
to help developers diagnose and resolve issues quickly.

Exception Categories:
- HiveFlowError: Base exception for all HiveFlow errors
- ValidationError: Input/validation errors
- BlackboardError: Blackboard storage/access errors
- SchedulerError: Task scheduling errors
- LLMError: LLM API/circuit breaker errors
- ConfigurationError: Config/setup errors
"""

from typing import Optional


class HiveFlowError(Exception):
    """
    Base exception for all HiveFlow errors.

    All HiveFlow exceptions should inherit from this class.
    Provides a fix_hint attribute with actionable guidance for resolving the error.

    Attributes:
        fix_hint: A actionable hint for fixing the error (e.g., "Check your LLM API key and network")
    """

    def __init__(self, message: str, fix_hint: Optional[str] = None):
        super().__init__(message)
        self.fix_hint = fix_hint or self._default_fix_hint()

    def _default_fix_hint(self) -> str:
        """Override this method to provide default fix hint for each exception type."""
        return "Check HiveFlow documentation at https://jdidjhdh.github.io/hiveflow/"

    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.fix_hint:
            return f"{base_msg}\n💡 Fix hint: {self.fix_hint}"
        return base_msg


# ============================================================================
# ValidationError - Input/Validation Errors
# ============================================================================


class ValidationError(HiveFlowError):
    """Raised when input validation fails."""

    def _default_fix_hint(self) -> str:
        return "Check your input parameters and ensure they match the expected format and constraints."


class UnsafeExpressionError(ValidationError):
    """Raised when expression contains disallowed operations."""

    def _default_fix_hint(self) -> str:
        return (
            "Only use safe operations: comparisons, arithmetic, logical operators. "
            "Function calls, imports, and attribute access are not allowed."
        )


class ObjectTooLargeError(ValidationError):
    """Raised when attempting to store an object exceeding max_object_size."""

    def __init__(
        self, message: str, object_size: int, max_size: int, key: Optional[str] = None, fix_hint: Optional[str] = None
    ):
        super().__init__(message, fix_hint)
        self.object_size = object_size
        self.max_size = max_size
        self.key = key

    def _default_fix_hint(self) -> str:
        return (
            f"Reduce object size below {self.max_size / (1024 * 1024):.1f}MB, "
            "or increase max_object_size in HiveFlowConfig."
        )

    def __str__(self) -> str:
        size_mb = self.object_size / (1024 * 1024)
        max_mb = self.max_size / (1024 * 1024)
        key_info = f" Key: '{self.key}'," if self.key else ""
        base_msg = f"{super(HiveFlowError, self).__str__()}{key_info} Size: {size_mb:.2f}MB, Max allowed: {max_mb:.2f}MB"
        if self.fix_hint:
            return f"{base_msg}\n💡 Fix hint: {self.fix_hint}"
        return base_msg


# ============================================================================
# BlackboardError - Blackboard Storage/Access Errors
# ============================================================================


class BlackboardError(HiveFlowError):
    """Base exception for blackboard-related errors."""

    pass


class BlackboardKeyError(BlackboardError, KeyError):
    """Raised when a key is not found in blackboard."""

    def _default_fix_hint(self) -> str:
        return (
            "Ensure the key exists in the blackboard before accessing it. "
            "Check if the agent has correct read_keys permissions."
        )


class BlackboardPermissionError(BlackboardError):
    """Raised when agent lacks permission to access blackboard key."""

    def _default_fix_hint(self) -> str:
        return "Update agent's read_keys or write_keys to grant access to the required blackboard keys."


# ============================================================================
# SchedulerError - Task Scheduling Errors
# ============================================================================


class SchedulerError(HiveFlowError):
    """Base exception for scheduler-related errors."""

    pass


class NoWorkerAvailableError(SchedulerError):
    """Raised when no worker is available to handle the task."""

    def _default_fix_hint(self) -> str:
        return (
            "Ensure at least one worker is registered with the required skills. "
            "Check worker queue sizes and increase if necessary."
        )


class TaskTimeoutError(SchedulerError):
    """Raised when a task execution times out."""

    def _default_fix_hint(self) -> str:
        return (
            "Increase task timeout in SchedulerConfig, or optimize worker performance. "
            "Check for deadlocks or resource bottlenecks."
        )


# ============================================================================
# OrchestratorError - Orchestration Errors
# ============================================================================


class OrchestratorError(HiveFlowError):
    """Base exception for orchestrator-related errors."""

    pass


class CycleDependencyError(OrchestratorError):
    """Raised when a cycle is detected in task dependencies."""

    def __init__(self, message: str, cycle_path: Optional[list[str]] = None, fix_hint: Optional[str] = None):
        super().__init__(message, fix_hint)
        self.cycle_path = cycle_path or []

    def _default_fix_hint(self) -> str:
        if self.cycle_path:
            return f"Remove circular dependency in task graph: {' -> '.join(self.cycle_path)}"
        return "Review task dependencies to remove circular references in the DAG."


# ============================================================================
# CheckpointError - Checkpoint/State Persistence Errors
# ============================================================================


class CheckpointError(HiveFlowError):
    """Base exception for checkpoint-related errors."""

    pass


class SchemaVersionMismatchError(CheckpointError):
    """Raised when checkpoint schema version is incompatible."""

    def __init__(self, checkpoint_version: str, current_version: str, fix_hint: Optional[str] = None):
        self.checkpoint_version = checkpoint_version
        self.current_version = current_version
        message = (
            f"Checkpoint schema version '{checkpoint_version}' is incompatible "
            f"with current version '{current_version}'."
        )
        super().__init__(message, fix_hint)

    def _default_fix_hint(self) -> str:
        return (
            "Migrate checkpoint data to the new schema version, "
            "or rebuild the checkpoint from scratch. Check CHANGELOG for migration instructions."
        )


# ============================================================================
# LLMError - LLM API/Circuit Breaker Errors
# ============================================================================


class LLMError(HiveFlowError):
    """Base exception for LLM-related errors."""

    pass


class CircuitBreakerOpenError(LLMError):
    """Raised when circuit breaker is open due to consecutive LLM failures."""

    def _default_fix_hint(self) -> str:
        return (
            "Check your LLM API key and network connectivity. "
            "Wait for circuit breaker timeout (default: 60s) before retrying. "
            "Monitor LLM service health and reduce request frequency if needed."
        )


class LLMAPIError(LLMError):
    """Raised when LLM API call fails."""

    def _default_fix_hint(self) -> str:
        return (
            "Check your LLM API key, base URL, and network connectivity. "
            "Verify API quotas and rate limits. Check LLM service status page."
        )


# ============================================================================
# MCPError - MCP Integration Errors
# ============================================================================


class MCPError(HiveFlowError):
    """Base exception for MCP-related errors."""

    pass


class ToolNameConflictError(MCPError):
    """Raised when attempting to register a tool with a name that already exists."""

    def __init__(self, tool_name: str, existing_plugin_id: str, new_plugin_id: str, fix_hint: Optional[str] = None):
        self.tool_name = tool_name
        self.existing_plugin_id = existing_plugin_id
        self.new_plugin_id = new_plugin_id
        message = (
            f"Tool name conflict: '{tool_name}' is already registered by plugin '{existing_plugin_id}'. "
            f"Cannot register from plugin '{new_plugin_id}'."
        )
        super().__init__(message, fix_hint)

    def _default_fix_hint(self) -> str:
        return (
            f"Rename your tool to avoid conflict with '{self.tool_name}', "
            f"or uninstall the conflicting plugin '{self.existing_plugin_id}'."
        )


# ============================================================================
# ConfigurationError - Configuration Errors
# ============================================================================


class ConfigurationError(HiveFlowError):
    """Raised when configuration is invalid or missing."""

    def _default_fix_hint(self) -> str:
        return "Check HiveFlowConfig settings and environment variables. Refer to configuration documentation."


class MissingDependencyError(ConfigurationError):
    """Raised when an optional dependency is required but not installed."""

    def __init__(self, package_name: str, extras_name: Optional[str] = None, fix_hint: Optional[str] = None):
        self.package_name = package_name
        self.extras_name = extras_name or package_name
        message = f"Missing dependency: {package_name}"
        super().__init__(message, fix_hint)

    def _default_fix_hint(self) -> str:
        return f"Install the required dependency: pip install hiveflow-core[{self.extras_name}]"


# ============================================================================
# Control Flow Exceptions (Not Errors)
# ============================================================================


class AbortExecutionException(Exception):
    """
    Exception to abort current task execution.

    This is a control flow exception, NOT an error.
    It's used to signal that a task should be aborted without retry.

    Note: This does NOT inherit from HiveFlowError since it's not an error condition.
    """

    def __init__(self, message: str = "Execution aborted"):
        super().__init__(message)