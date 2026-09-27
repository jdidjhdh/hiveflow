"""HiveFlow Timezone Utilities

Provides utilities for handling timezone conversions and formatting.
All audit logs and checkpoint metadata store timestamps in UTC.
This module provides helpers to convert UTC timestamps to local time for display.

Usage:
    from hiveflow.utils import format_local_time, utc_now

    # Get current UTC time
    timestamp = utc_now()

    # Format for display (converts to local timezone)
    formatted = format_local_time(timestamp)
    print(formatted)  # "2024-01-15 14:30:25 CST"

    # Format with specific timezone
    from zoneinfo import ZoneInfo
    formatted = format_local_time(timestamp, tz=ZoneInfo("America/New_York"))
"""

import datetime
from datetime import datetime, timezone
from typing import Union
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """
    Get current UTC datetime.

    Returns:
        Current datetime in UTC timezone
    """
    return datetime.now(timezone.utc)


def format_local_time(
    timestamp: Union[datetime, float, str, None],
    tz: Union[ZoneInfo, datetime.tzinfo, None] = None,
    format_str: str = "%Y-%m-%d %H:%M:%S %Z",
) -> str:
    """
    Convert UTC timestamp to local timezone and format for display.

    Args:
        timestamp: Input timestamp in one of the following formats:
            - datetime: datetime object (assumed UTC if no timezone)
            - float: Unix timestamp (seconds since epoch, UTC)
            - str: ISO 8601 formatted string (assumed UTC if no timezone)
            - None: Returns "N/A"
        tz: Target timezone for display. If None, uses local system timezone.
        format_str: strftime format string. Default: "%Y-%m-%d %H:%M:%S %Z"

    Returns:
        Formatted datetime string in local timezone

    Examples:
        >>> from hiveflow.utils import format_local_time
        >>> format_local_time(1642234567.89)  # Unix timestamp
        "2022-01-15 14:30:25 CST"
        >>> format_local_time("2022-01-15T06:30:25Z")  # ISO 8601
        "2022-01-15 14:30:25 CST"
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2022, 1, 15, 6, 30, 25, tzinfo=timezone.utc)
        >>> format_local_time(dt)
        "2022-01-15 14:30:25 CST"
    """
    if timestamp is None:
        return "N/A"

    # Convert input to UTC datetime
    utc_dt: datetime

    if isinstance(timestamp, datetime):
        # datetime object - ensure it has timezone
        if timestamp.tzinfo is None:
            # Assume UTC if no timezone specified
            utc_dt = timestamp.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC
            utc_dt = timestamp.astimezone(timezone.utc)

    elif isinstance(timestamp, (float, int)):
        # Unix timestamp (seconds since epoch)
        utc_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)

    elif isinstance(timestamp, str):
        # ISO 8601 string
        try:
            # Try parsing with timezone
            parsed_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed_dt.tzinfo is None:
                # Assume UTC if no timezone in string
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            utc_dt = parsed_dt.astimezone(timezone.utc)
        except ValueError:
            # Fallback: try common formats
            try:
                # Try "%Y-%m-%d %H:%M:%S" format
                parsed_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                utc_dt = parsed_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                # Return original string if parsing fails
                return f"(parse error: {timestamp})"

    else:
        # Unsupported type
        return f"(unsupported type: {type(timestamp).__name__})"

    # Convert to target timezone
    target_tz = tz if tz is not None else _get_local_timezone()
    local_dt = utc_dt.astimezone(target_tz)

    # Format
    return local_dt.strftime(format_str)


def _get_local_timezone() -> datetime.tzinfo:
    """
    Get local system timezone.

    Returns:
        Local timezone info object
    """
    # Try to get local timezone
    try:
        # Python 3.9+: use ZoneInfo
        import datetime

        # Get local timezone from system
        local_tz = datetime.datetime.now().astimezone().tzinfo
        return local_tz
    except Exception:
        # Fallback to UTC
        return timezone.utc


def parse_utc_timestamp(timestamp: Union[datetime, float, str]) -> datetime:
    """
    Parse timestamp to UTC datetime object.

    Args:
        timestamp: Input timestamp (datetime, float, or ISO 8601 string)

    Returns:
        datetime object in UTC timezone

    Raises:
        ValueError: If timestamp string cannot be parsed
    """
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    elif isinstance(timestamp, (float, int)):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    elif isinstance(timestamp, str):
        try:
            parsed_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed_dt.tzinfo is None:
                return parsed_dt.replace(tzinfo=timezone.utc)
            return parsed_dt.astimezone(timezone.utc)
        except ValueError as e:
            raise ValueError(f"Cannot parse timestamp string: {timestamp}") from e

    else:
        raise TypeError(f"Unsupported timestamp type: {type(timestamp).__name__}")


def timestamp_to_iso(timestamp: Union[datetime, float, None]) -> str:
    """
    Convert timestamp to ISO 8601 UTC string for storage.

    Args:
        timestamp: Input timestamp (datetime, float, or None)

    Returns:
        ISO 8601 formatted string in UTC (e.g., "2022-01-15T06:30:25Z")
        Returns empty string if timestamp is None
    """
    if timestamp is None:
        return ""

    utc_dt = parse_utc_timestamp(timestamp)
    # Use 'Z' suffix for UTC
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")