"""Ingestion reliability patterns (DATA-17).

Blueprint Part 32.2 (l.1304-1306): idempotency (dedupe by deterministic event_id),
retries-with-backoff, dead-letter queues for poison messages, backpressure handling
(Part 18). Circuit-breaker/bulkhead patterns are owned by BACKEND/PLATFORM; we expose
the dedupe/DLQ/backpressure/retry hooks the ingest path needs.

Status: REAL pure-python (numpy/pandas/pyarrow only). Deterministic: no randomness;
backoff sleeps are optional and disabled by default so tests stay fast.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Callable, Optional


class Deduper:
    """Idempotent dedupe by deterministic event_id (Part 32.2 idempotency).

    seen(event_id) returns True the FIRST time and False on every duplicate, so the
    ingest path drops replays. Backed by deterministic event_id from make_id(...),
    which the normalizer (DATA-5) guarantees for identical raw rows.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.dropped = 0

    def is_new(self, event_id: str) -> bool:
        if event_id in self._seen:
            self.dropped += 1
            return False
        self._seen.add(event_id)
        return True

    def __contains__(self, event_id: str) -> bool:
        return event_id in self._seen

    def __len__(self) -> int:
        return len(self._seen)


class DeadLetterQueue:
    """Holds poison messages that failed processing/validation (Part 32.2 DLQ)."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def put(self, msg: dict[str, Any], reason: str) -> None:
        self.items.append({"reason": reason, "msg": msg})

    def __len__(self) -> int:
        return len(self.items)

    def reasons(self) -> list[str]:
        return [it["reason"] for it in self.items]


class BackpressureBuffer:
    """Bounded buffer modelling backpressure (Part 32.2/Part 18).

    offer() returns False when the buffer is full (signalling upstream to slow down)
    instead of growing without bound. drain() pops up to `n` ready items.
    """

    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self._q: deque[Any] = deque()
        self.rejected = 0

    def offer(self, item: Any) -> bool:
        if len(self._q) >= self.capacity:
            self.rejected += 1
            return False
        self._q.append(item)
        return True

    def drain(self, n: int = 1) -> list[Any]:
        out: list[Any] = []
        for _ in range(n):
            if not self._q:
                break
            out.append(self._q.popleft())
        return out

    def __len__(self) -> int:
        return len(self._q)

    @property
    def full(self) -> bool:
        return len(self._q) >= self.capacity


def retry_with_backoff(
    fn: Callable[[], Any],
    retries: int = 3,
    base_delay: float = 0.0,
    factor: float = 2.0,
    sleep: Optional[Callable[[float], None]] = None,
    on_giveup: Optional[Callable[[Exception], None]] = None,
) -> Any:
    """Call `fn`, retrying on exception with exponential backoff (Part 32.2).

    base_delay=0.0 by default => no real sleeping (fast/deterministic for tests).
    Pass a sleep callable to actually wait. Re-raises the last error after `retries`
    attempts unless on_giveup handles it.
    """
    attempt = 0
    delay = base_delay
    last_exc: Optional[Exception] = None
    while attempt <= retries:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - reliability boundary
            last_exc = exc
            attempt += 1
            if attempt > retries:
                break
            if sleep is not None and delay > 0:
                sleep(delay)
            delay = delay * factor if delay > 0 else base_delay
    if on_giveup is not None and last_exc is not None:
        on_giveup(last_exc)
        return None
    assert last_exc is not None
    raise last_exc


class ReliableIngest:
    """Compose dedupe + DLQ + backpressure + retry around a process function.

    handle(event_id, msg) -> "accepted" | "duplicate" | "rejected" | "dead_lettered".
    A poison message (process raises after retries) lands in the DLQ instead of
    crashing the pipeline.
    """

    def __init__(
        self,
        process: Callable[[dict], None],
        capacity: int = 1000,
        retries: int = 2,
    ) -> None:
        self.process = process
        self.deduper = Deduper()
        self.dlq = DeadLetterQueue()
        self.buffer = BackpressureBuffer(capacity=capacity)
        self.retries = retries
        self.accepted = 0

    def handle(self, event_id: str, msg: dict) -> str:
        if not self.deduper.is_new(event_id):
            return "duplicate"
        if not self.buffer.offer((event_id, msg)):
            return "rejected"          # backpressure: caller should slow down
        self.buffer.drain(1)           # immediate drain in the sync fallback
        try:
            retry_with_backoff(lambda: self.process(msg), retries=self.retries)
        except Exception as exc:        # noqa: BLE001
            self.dlq.put(msg, reason=f"{type(exc).__name__}: {exc}")
            return "dead_lettered"
        self.accepted += 1
        return "accepted"
