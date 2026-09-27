"""
Circuit Breaker for LLM API calls.

Implements the circuit breaker pattern to prevent cascading failures
when calling external LLM services.

Prometheus Metrics:
- circuit_breaker_state: Gauge indicating current state (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
  Label: llm_client_id for identifying different LLM clients
"""

import time
from enum import Enum
from threading import Lock
from typing import Deque
from collections import deque

# Prometheus metrics support with fallback
_PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import Gauge
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    # Mock Gauge for environments without prometheus_client
    class MockGauge:
        """Mock Gauge when prometheus_client is not available."""
        def __init__(self, name: str, description: str, labelnames: list[str] | None = None):
            self._name = name
            self._description = description
            self._labelnames = labelnames or []
            self._values: dict[str, float] = {}
        
        def labels(self, **kwargs):
            key = tuple(sorted(kwargs.items()))
            return MockGaugeChild(self, key)
        
        def set(self, value: float):
            pass
        
        def _set_value(self, key: tuple, value: float):
            self._values[str(key)] = value
    
    class MockGaugeChild:
        """Child gauge for labeled metrics."""
        def __init__(self, parent: MockGauge, key: tuple):
            self._parent = parent
            self._key = key
        
        def set(self, value: float):
            self._parent._set_value(self._key, value)
    
    Gauge = MockGauge  # type: ignore


# Circuit breaker state metric (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
CIRCUIT_BREAKER_STATE_Gauge = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state: 0=CLOSED (normal), 1=HALF_OPEN (testing), 2=OPEN (failing)",
    ["llm_client_id"],
)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests flow through
    OPEN = "open"  # Circuit tripped, requests are blocked
    HALF_OPEN = "half_open"  # Testing if service recovered

    def to_metric_value(self) -> int:
        """Convert state to Prometheus metric value."""
        if self == CircuitState.CLOSED:
            return 0
        elif self == CircuitState.HALF_OPEN:
            return 1
        elif self == CircuitState.OPEN:
            return 2
        return 0


class CircuitBreaker:
    """
    Circuit breaker for protecting LLM API calls.

    Implements sliding window failure counting with three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit tripped, requests blocked for recovery period
    - HALF_OPEN: Testing recovery, allows limited requests

    Prometheus Metrics:
    - circuit_breaker_state: Gauge with label llm_client_id
      Values: 0 (CLOSED), 1 (HALF_OPEN), 2 (OPEN)

    Args:
        failure_threshold: Number of failures within window to trip circuit (default: 5)
        window_seconds: Sliding window duration in seconds (default: 60)
        recovery_timeout: Seconds to wait before attempting recovery (default: 30)
        client_id: Identifier for Prometheus metrics label (default: "default")
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        window_seconds: int = 60,
        recovery_timeout: int = 30,
        client_id: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_timeout = recovery_timeout
        self.client_id = client_id

        self._state = CircuitState.CLOSED
        self._last_failure_time: float | None = None
        self._failure_times: Deque[float] = deque()
        self._lock = Lock()
        
        # Initialize Prometheus metric
        self._metric = CIRCUIT_BREAKER_STATE_Gauge.labels(llm_client_id=client_id)
        self._update_metric()

    def _update_metric(self) -> None:
        """Update Prometheus gauge with current state."""
        try:
            self._metric.set(self._state.to_metric_value())
        except Exception:
            pass  # Silently ignore metric update failures

    def can_execute(self) -> bool:
        """
        Check if a request can be executed based on current circuit state.

        Returns:
            True if request can proceed, False if circuit is open
        """
        with self._lock:
            current_time = time.monotonic()

            if self._state == CircuitState.CLOSED:
                return True

            elif self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if self._last_failure_time is None:
                    self._state = CircuitState.HALF_OPEN
                    self._update_metric()
                    return True

                time_since_failure = current_time - self._last_failure_time
                if time_since_failure >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._update_metric()
                    return True

                return False

            elif self._state == CircuitState.HALF_OPEN:
                # Allow request to test if service recovered
                return True

            return False

    def record_success(self) -> None:
        """
        Record a successful request.

        If in HALF_OPEN state, transitions to CLOSED.
        Clears failure history on success.
        """
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Service recovered, close circuit
                self._state = CircuitState.CLOSED
                self._failure_times.clear()
                self._last_failure_time = None
                self._update_metric()

    def record_failure(self) -> None:
        """
        Record a failed request.

        Tracks failures in sliding window and trips circuit if threshold exceeded.
        """
        with self._lock:
            current_time = time.monotonic()

            # Add failure to sliding window
            self._failure_times.append(current_time)
            self._last_failure_time = current_time

            # Remove failures outside the window
            window_start = current_time - self.window_seconds
            while self._failure_times and self._failure_times[0] < window_start:
                self._failure_times.popleft()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test, reopen circuit
                self._state = CircuitState.OPEN
                self._update_metric()

            elif self._state == CircuitState.CLOSED:
                # Check if threshold exceeded
                if len(self._failure_times) >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._update_metric()

    def get_state(self) -> CircuitState:
        """
        Get current circuit state.

        Returns:
            Current CircuitState enum value
        """
        with self._lock:
            # Update state based on time elapsed
            if self._state == CircuitState.OPEN and self._last_failure_time is not None:
                current_time = time.monotonic()
                if current_time - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._update_metric()

            return self._state

    def reset(self) -> None:
        """
        Reset circuit breaker to initial state.

        Clears all failure history and sets state to CLOSED.
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_times.clear()
            self._last_failure_time = None
            self._update_metric()

    def get_failure_count(self) -> int:
        """
        Get current count of failures in the sliding window.

        Returns:
            Number of failures within the window
        """
        with self._lock:
            current_time = time.monotonic()
            window_start = current_time - self.window_seconds

            # Count failures within window
            return sum(1 for t in self._failure_times if t >= window_start)