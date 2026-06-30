"""Graceful degradation to L1-rules-only (BACKEND-15, blueprint Part 18.1 l.591 / 30.1).

When the model server is unavailable the online path falls back to **L1 rules only**, marks the
affected events for re-scoring, and never goes dark. This controller tracks model-server health,
exposes the current mode, and holds the re-score backlog that a healthy serving tier drains later.
"""

from __future__ import annotations

import threading

from app.observability.metrics import DEGRADED_MODE


class DegradationController:
    def __init__(self) -> None:
        self._degraded = False
        self._rescore: list[str] = []
        self._lock = threading.Lock()
        DEGRADED_MODE.set(0)

    @property
    def degraded(self) -> bool:
        return self._degraded

    def enter_degraded(self) -> None:
        with self._lock:
            self._degraded = True
            DEGRADED_MODE.set(1)

    def recover(self) -> list[str]:
        """Leave degraded mode and return the backlog of event_ids to re-score."""
        with self._lock:
            self._degraded = False
            DEGRADED_MODE.set(0)
            backlog = list(self._rescore)
            self._rescore.clear()
            return backlog

    def mark_for_rescore(self, event_id: str) -> None:
        with self._lock:
            self._rescore.append(event_id)

    def pending_rescore(self) -> list[str]:
        with self._lock:
            return list(self._rescore)


DEGRADATION = DegradationController()
