"""Token Quota Control for HiveFlow LLM operations.

Provides daily token usage tracking with alerts and circuit breaking.
"""

import asyncio
import logging
import threading
from collections.abc import Callable
from datetime import datetime, time
from typing import Any

logger = logging.getLogger(__name__)


class TokenQuotaExceededError(Exception):
    """Raised when token quota is exceeded."""
    pass


class TokenQuota:
    """
    Token quota management with daily reset, alerts, and circuit breaking.

    Features:
    - Daily token quota (default: 1,000,000 tokens)
    - Alert callback when approaching limit (default: 80%)
    - Automatic circuit breaking when quota exhausted
    - Midnight reset of daily usage
    - Thread-safe and async-safe

    Usage:
        quota = TokenQuota(daily_limit=1_000_000)

        # Set alert callback
        quota.set_alert_callback(lambda info: logger.warning(f"Quota alert: {info}"))

        # Check before consuming
        if quota.check_quota(1000):
            quota.consume(1000)

        # Get usage stats
        stats = quota.get_usage()
    """

    def __init__(
        self,
        daily_limit: int = 1_000_000,
        alert_threshold: float = 0.8,
        auto_reset: bool = True,
    ):
        """
        Initialize token quota.

        Args:
            daily_limit: Maximum tokens per day (default: 1,000,000)
            alert_threshold: Threshold for alerts (0.0-1.0, default: 0.8)
            auto_reset: Automatically reset at midnight (default: True)
        """
        self.daily_limit = daily_limit
        self.alert_threshold = alert_threshold
        self.auto_reset = auto_reset

        self._daily_usage = 0
        self._last_reset_date = datetime.now().date()
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._alert_callback: Callable[[dict[str, Any]], None] | None = None
        self._circuit_breaker = False
        self._alert_triggered = False  # Track if alert was already triggered

    def set_alert_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        """
        Set callback for quota alerts.

        Args:
            callback: Function to call when approaching limit.
                     Receives dict with 'usage', 'limit', 'percentage', 'action'.
                     Set to None to disable alerts.
        """
        self._alert_callback = callback

    def _check_and_reset_if_new_day(self) -> None:
        """Check if it's a new day and reset if needed."""
        today = datetime.now().date()
        if today > self._last_reset_date:
            logger.info(
                f"Token quota auto-reset: {self._daily_usage} tokens used on {self._last_reset_date}"
            )
            self._daily_usage = 0
            self._last_reset_date = today
            self._circuit_breaker = False
            self._alert_triggered = False

    def check_quota(self, tokens: int) -> bool:
        """
        Check if tokens can be consumed without exceeding quota.

        Thread-safe check that also handles midnight reset.

        Args:
            tokens: Number of tokens to check

        Returns:
            True if tokens can be consumed, False if would exceed quota
        """
        with self._lock:
            if self.auto_reset:
                self._check_and_reset_if_new_day()

            if self._circuit_breaker:
                return False

            return (self._daily_usage + tokens) <= self.daily_limit

    def consume(self, tokens: int) -> None:
        """
        Consume tokens from the daily quota.

        Args:
            tokens: Number of tokens to consume

        Raises:
            TokenQuotaExceededError: If consuming would exceed quota

        Note:
            Use check_quota() first to verify availability.
        """
        with self._lock:
            if self.auto_reset:
                self._check_and_reset_if_new_day()

            if self._circuit_breaker:
                raise TokenQuotaExceededError(
                    f"Circuit breaker active. Quota exceeded: {self._daily_usage}/{self.daily_limit}"
                )

            if (self._daily_usage + tokens) > self.daily_limit:
                self._circuit_breaker = True
                self._trigger_alert("circuit_breaker", tokens)
                raise TokenQuotaExceededError(
                    f"Token quota exceeded: {self._daily_usage + tokens}/{self.daily_limit}"
                )

            self._daily_usage += tokens

            # Check if we've crossed the alert threshold
            percentage = self._daily_usage / self.daily_limit
            if percentage >= self.alert_threshold and not self._alert_triggered:
                self._alert_triggered = True
                self._trigger_alert("threshold_warning", tokens)

    def reset(self) -> None:
        """
        Manually reset the daily usage counter.

        This also clears the circuit breaker and alert state.
        """
        with self._lock:
            logger.info(f"Token quota manual reset: was {self._daily_usage} tokens")
            self._daily_usage = 0
            self._last_reset_date = datetime.now().date()
            self._circuit_breaker = False
            self._alert_triggered = False

    def get_usage(self) -> dict[str, Any]:
        """
        Get current usage statistics.

        Returns:
            Dict with usage info:
            - daily_usage: Current day's token usage
            - daily_limit: Maximum tokens per day
            - remaining: Tokens remaining for today
            - percentage: Usage percentage (0-100)
            - circuit_breaker: Whether circuit breaker is active
            - last_reset: Date of last reset
        """
        with self._lock:
            if self.auto_reset:
                self._check_and_reset_if_new_day()

            remaining = max(0, self.daily_limit - self._daily_usage)
            percentage = (self._daily_usage / self.daily_limit) * 100 if self.daily_limit > 0 else 0

            return {
                "daily_usage": self._daily_usage,
                "daily_limit": self.daily_limit,
                "remaining": remaining,
                "percentage": round(percentage, 2),
                "circuit_breaker": self._circuit_breaker,
                "last_reset": self._last_reset_date.isoformat(),
            }

    def _trigger_alert(self, action: str, attempted_tokens: int = 0) -> None:
        """
        Trigger alert callback if set.

        Args:
            action: Type of alert ('threshold_warning' or 'circuit_breaker')
            attempted_tokens: Tokens that triggered the alert
        """
        if self._alert_callback is None:
            return

        try:
            alert_info = {
                "action": action,
                "daily_usage": self._daily_usage,
                "daily_limit": self.daily_limit,
                "percentage": round((self._daily_usage / self.daily_limit) * 100, 2),
                "remaining": max(0, self.daily_limit - self._daily_usage),
                "attempted_tokens": attempted_tokens,
                "circuit_breaker": self._circuit_breaker,
            }
            self._alert_callback(alert_info)
        except Exception as e:
            logger.error(f"Error in token quota alert callback: {e}")

    # Async versions for async code

    async def check_quota_async(self, tokens: int) -> bool:
        """Async version of check_quota."""
        async with self._async_lock:
            if self.auto_reset:
                self._check_and_reset_if_new_day()

            if self._circuit_breaker:
                return False

            return (self._daily_usage + tokens) <= self.daily_limit

    async def consume_async(self, tokens: int) -> None:
        """Async version of consume."""
        async with self._async_lock:
            if self.auto_reset:
                self._check_and_reset_if_new_day()

            if self._circuit_breaker:
                raise TokenQuotaExceededError(
                    f"Circuit breaker active. Quota exceeded: {self._daily_usage}/{self.daily_limit}"
                )

            if (self._daily_usage + tokens) > self.daily_limit:
                self._circuit_breaker = True
                self._trigger_alert("circuit_breaker", tokens)
                raise TokenQuotaExceededError(
                    f"Token quota exceeded: {self._daily_usage + tokens}/{self.daily_limit}"
                )

            self._daily_usage += tokens

            percentage = self._daily_usage / self.daily_limit
            if percentage >= self.alert_threshold and not self._alert_triggered:
                self._alert_triggered = True
                self._trigger_alert("threshold_warning", tokens)

    async def get_usage_async(self) -> dict[str, Any]:
        """Async version of get_usage."""
        async with self._async_lock:
            if self.auto_reset:
                self._check_and_reset_if_new_day()

            remaining = max(0, self.daily_limit - self._daily_usage)
            percentage = (self._daily_usage / self.daily_limit) * 100 if self.daily_limit > 0 else 0

            return {
                "daily_usage": self._daily_usage,
                "daily_limit": self.daily_limit,
                "remaining": remaining,
                "percentage": round(percentage, 2),
                "circuit_breaker": self._circuit_breaker,
                "last_reset": self._last_reset_date.isoformat(),
            }


# Global default instance
_default_quota: TokenQuota | None = None
_default_lock = threading.Lock()


def get_default_quota() -> TokenQuota:
    """Get or create the default global TokenQuota instance."""
    global _default_quota
    if _default_quota is None:
        with _default_lock:
            if _default_quota is None:
                _default_quota = TokenQuota()
    return _default_quota


def set_default_quota(quota: TokenQuota) -> None:
    """Set the default global TokenQuota instance."""
    global _default_quota
    with _default_lock:
        _default_quota = quota