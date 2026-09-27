"""HiveFlow Environment Variable Utilities

Provides helpers for accessing environment variables with unified HIVEFLOW_ prefix
and backward compatibility warnings for deprecated variable names.

All HiveFlow-specific environment variables should use HIVEFLOW_ prefix.
For external integrations (OpenAI, Anthropic, OTEL), standard prefixes are preserved.

Deprecated Variables (will be removed in v2.0):
- OPENAI_API_KEY → HIVEFLOW_OPENAI_API_KEY
- OPENAI_BASE_URL → HIVEFLOW_OPENAI_BASE_URL
- AZURE_OPENAI_ENDPOINT → HIVEFLOW_AZURE_OPENAI_ENDPOINT
- ANTHROPIC_API_KEY → HIVEFLOW_ANTHROPIC_API_KEY
- HOSTNAME → HIVEFLOW_HOSTNAME
"""

import os
import warnings
from typing import Optional


# Deprecated environment variable mappings
_DEPRECATED_ENV_VARS = {
    # LLM API Keys
    "OPENAI_API_KEY": "HIVEFLOW_OPENAI_API_KEY",
    "OPENAI_BASE_URL": "HIVEFLOW_OPENAI_BASE_URL",
    "AZURE_OPENAI_ENDPOINT": "HIVEFLOW_AZURE_OPENAI_ENDPOINT",
    "ANTHROPIC_API_KEY": "HIVEFLOW_ANTHROPIC_API_KEY",
    # Observability
    "HOSTNAME": "HIVEFLOW_HOSTNAME",
    "OTEL_SERVICE_NAME": "HIVEFLOW_OTEL_SERVICE_NAME",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "HIVEFLOW_OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_TRACES_SAMPLER_ARG": "HIVEFLOW_OTEL_TRACES_SAMPLER_ARG",
}


def get_env_with_prefix(
    key: str,
    default: Optional[str] = None,
    prefix: str = "HIVEFLOW",
    warn_deprecated: bool = True,
) -> Optional[str]:
    """
    Get environment variable with HIVEFLOW_ prefix and backward compatibility.

    Args:
        key: Environment variable name (without prefix)
        default: Default value if not found
        prefix: Prefix to use (default: "HIVEFLOW")
        warn_deprecated: Whether to warn about deprecated variable names

    Returns:
        Environment variable value or default

    Examples:
        >>> get_env_with_prefix("MAX_CONCURRENCY", "10")
        # Reads HIVEFLOW_MAX_CONCURRENCY, warns if MAX_CONCURRENCY is used
        "10"

        >>> get_env_with_prefix("OPENAI_API_KEY", "")
        # Reads HIVEFLOW_OPENAI_API_KEY first, then OPENAI_API_KEY with warning
        "sk-..."
    """
    # Try new prefixed variable first
    prefixed_key = f"{prefix}_{key}"
    value = os.environ.get(prefixed_key)

    if value is not None:
        return value

    # Try deprecated unprefixed variable
    unprefixed_key = key
    deprecated_value = os.environ.get(unprefixed_key)

    if deprecated_value is not None and warn_deprecated and unprefixed_key in _DEPRECATED_ENV_VARS:
        # Issue deprecation warning
        warnings.warn(
            f"Environment variable '{unprefixed_key}' is deprecated and will be removed in HiveFlow v2.0. "
            f"Use '{prefixed_key}' instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return deprecated_value

    # Return default
    return default


def get_hiveflow_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get HiveFlow-specific environment variable with HIVEFLOW_ prefix.

    Args:
        key: Variable name without prefix (e.g., "MAX_CONCURRENCY")
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    return get_env_with_prefix(key, default, prefix="HIVEFLOW")


def get_llm_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get LLM API environment variable with backward compatibility.

    Supports both standard names (OPENAI_API_KEY) and prefixed names (HIVEFLOW_OPENAI_API_KEY).
    Prefixed names are preferred, unprefixed names trigger deprecation warning.

    Args:
        key: Variable name (e.g., "OPENAI_API_KEY")
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    # For LLM keys, first try prefixed version, then unprefixed with warning
    prefixed_key = f"HIVEFLOW_{key}"
    value = os.environ.get(prefixed_key)

    if value is not None:
        return value

    # Try unprefixed (standard) variable
    unprefixed_value = os.environ.get(key, default)

    if unprefixed_value is not None and unprefixed_value != default:
        # Issue deprecation warning for unprefixed usage
        warnings.warn(
            f"Environment variable '{key}' is deprecated in HiveFlow context. "
            f"Consider using '{prefixed_key}' for better consistency, "
            f"though '{key}' will continue to work for backward compatibility.",
            DeprecationWarning,
            stacklevel=3,
        )

    return unprefixed_value


def get_otel_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get OpenTelemetry environment variable with backward compatibility.

    OTEL_* variables are standard and will be preserved.
    HIVEFLOW_OTEL_* variables are HiveFlow-specific aliases.

    Args:
        key: Variable name (e.g., "OTEL_SERVICE_NAME" or "HIVEFLOW_OTEL_ENABLED")
        default: Default value if not found

    Returns:
        Environment variable value or default
    """
    # Check if already prefixed
    if key.startswith("HIVEFLOW_"):
        return os.environ.get(key, default)

    # Try HiveFlow-prefixed version first
    prefixed_key = f"HIVEFLOW_{key}"
    value = os.environ.get(prefixed_key)

    if value is not None:
        return value

    # Fall back to standard OTEL_* variable (no warning, as these are standard)
    return os.environ.get(key, default)