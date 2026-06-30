"""Dead-letter queue (BACKEND-14, blueprint Part 32.2).

Events that fail processing after retries land here instead of being lost, with the failure reason
attached for later replay. # STUB: DATA/PLATFORM own the real Kafka DLQ topic; this is the
in-process shim the online path writes to.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DeadLetter:
    event_id: str
    reason: str
    payload: dict = field(default_factory=dict)


class DeadLetterQueue:
    def __init__(self) -> None:
        self._items: list[DeadLetter] = []

    def put(self, event_id: str, reason: str, payload: dict | None = None) -> None:
        self._items.append(DeadLetter(event_id=event_id, reason=reason, payload=payload or {}))

    def items(self) -> list[DeadLetter]:
        return list(self._items)

    def drain(self) -> list[DeadLetter]:
        out = list(self._items)
        self._items.clear()
        return out

    def __len__(self) -> int:
        return len(self._items)


DLQ = DeadLetterQueue()
