"""Retry-with-backoff (BACKEND-14, blueprint Part 32.2).

Bounded exponential backoff with optional jitter. Used around transient dependency calls. Jitter
uses a deterministic per-attempt offset (no global RNG) so tests are reproducible.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.05,
    max_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Call ``fn`` up to ``attempts`` times with exponential backoff; re-raise the last error."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on as exc:  # noqa: PERF203
            last = exc
            if attempt == attempts - 1:
                break
            delay = min(max_delay, base_delay * (2**attempt))
            # deterministic jitter in [0, 0.5*delay)
            jitter = (attempt % 3) / 3.0 * 0.5 * delay
            sleep(delay + jitter)
    assert last is not None
    raise last
