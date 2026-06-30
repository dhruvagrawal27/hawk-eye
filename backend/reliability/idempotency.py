"""Idempotency / exactly-once keying (BACKEND-14, blueprint Part 18.1 l.590).

Deterministic ``event_id`` keying so a replay never double-alerts. In production this is backed by
Flink checkpointing + Kafka transactions; here an in-memory keyed set provides the dedupe semantics
the online path relies on (and that the idempotency test asserts).
"""

from __future__ import annotations

import threading


class IdempotencyStore:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def seen(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._seen

    def mark(self, event_id: str) -> bool:
        """Mark an event processed. Returns True if newly marked, False if it was already seen."""
        with self._lock:
            if event_id in self._seen:
                return False
            self._seen.add(event_id)
            return True

    def reset(self) -> None:
        with self._lock:
            self._seen.clear()

    def __len__(self) -> int:
        return len(self._seen)


DEDUPE = IdempotencyStore()
