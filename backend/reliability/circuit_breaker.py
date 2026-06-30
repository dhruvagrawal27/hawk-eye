"""Circuit breaker (BACKEND-14, blueprint Part 32.2 l.1305).

Closed → Open (after N consecutive failures) → Half-Open (after a cooldown) → Closed (on success).
Protects calls to the model-serving / feature-store dependencies; when Open, the online path takes
the graceful-degradation branch instead of hammering a dead dependency.
"""

from __future__ import annotations

import time
from enum import Enum


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, *, failure_threshold: int = 5, reset_timeout: float = 10.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = State.CLOSED
        self._opened_at = 0.0

    @property
    def state(self) -> State:
        if self._state == State.OPEN and (time.monotonic() - self._opened_at) >= self.reset_timeout:
            self._state = State.HALF_OPEN
        return self._state

    def allow(self) -> bool:
        """Whether a call is currently permitted."""
        return self.state in (State.CLOSED, State.HALF_OPEN)

    def record_success(self) -> None:
        self._failures = 0
        self._state = State.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = State.OPEN
            self._opened_at = time.monotonic()

    def call(self, fn, *args, **kwargs):
        """Run ``fn`` through the breaker. Raises ``CircuitOpenError`` when Open."""
        if not self.allow():
            raise CircuitOpenError("circuit open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result


class CircuitOpenError(Exception):
    pass
