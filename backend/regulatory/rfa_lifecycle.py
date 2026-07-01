"""M2.5 — RFA lifecycle state machine + staff-accountability 6-month clock (RBI Master Directions
on Fraud Risk Management 2024).

Turns the boolean RFA *tag* (``regulatory.rfa.tag``) into a governed lifecycle:

    TRIGGERED ──▶ UNDER_EXAMINATION ──▶ CONFIRMED ──▶ CLOSED
        └───────────────────────────────────────────▶ CLOSED (exonerated)

with a hard **6-month (180-day) staff-accountability examination clock** and a **natural-justice
show-cause gate**: a person can be moved to CONFIRMED only by a human AND only after a show-cause
response is recorded (SBI v Rajesh Agarwal). ALERT-ONLY: nothing here classifies a person
automatically; every transition is a human action, audited. Window-expiry is surfaced as a nudge
(alert-only), never an auto-close.

State is in-process; persisting to the governance DB is SCAFFOLD (``snapshot``/``restore`` seams).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from regulatory.util import add_days, parse

EXAMINATION_WINDOW_DAYS = 180   # RBI staff-accountability 6-month clock
SHOW_CAUSE_DUE_DAYS = 30        # natural-justice show-cause deadline


class RfaState(str, Enum):
    TRIGGERED = "triggered"
    UNDER_EXAMINATION = "under_examination"
    CONFIRMED = "confirmed"
    CLOSED = "closed"


# Allowed transitions (from -> {to}).
_TRANSITIONS: dict[RfaState, set[RfaState]] = {
    RfaState.TRIGGERED: {RfaState.UNDER_EXAMINATION, RfaState.CLOSED},
    RfaState.UNDER_EXAMINATION: {RfaState.CONFIRMED, RfaState.CLOSED},
    RfaState.CONFIRMED: {RfaState.CLOSED},
    RfaState.CLOSED: set(),
}


class RfaTransitionError(ValueError):
    """Raised on an illegal state transition or a natural-justice / window violation."""


@dataclass
class RfaExamination:
    entity_id: str
    state: str
    triggered_ts: str
    examination_due_ts: str
    show_cause_due_ts: str
    alert_id: str | None = None
    show_cause_response_ts: str | None = None
    closed_ts: str | None = None
    outcome: str | None = None            # confirmed | exonerated
    triggers: list[str] = field(default_factory=list)

    def window_expired(self, now_ts: str) -> bool:
        return parse(now_ts) > parse(self.examination_due_ts)

    def to_dict(self) -> dict:
        return asdict(self)


def validate_transition(src: RfaState, dst: RfaState) -> None:
    if dst not in _TRANSITIONS.get(src, set()):
        raise RfaTransitionError(f"illegal RFA transition {src.value} -> {dst.value}")


class RfaLifecycleService:
    """In-memory RFA lifecycle store keyed by entity_id (one open examination per entity)."""

    def __init__(self) -> None:
        self._store: dict[str, RfaExamination] = {}

    # --- lifecycle ---
    def trigger(
        self, entity_id: str, *, triggered_ts: str, alert_id: str | None = None,
        triggers: list[str] | None = None,
    ) -> RfaExamination:
        """Open (or return the existing) RFA examination for an entity. Idempotent per entity."""
        existing = self._store.get(entity_id)
        if existing is not None and existing.state != RfaState.CLOSED.value:
            return existing
        exam = RfaExamination(
            entity_id=entity_id,
            state=RfaState.TRIGGERED.value,
            triggered_ts=triggered_ts,
            examination_due_ts=add_days(triggered_ts, EXAMINATION_WINDOW_DAYS),
            show_cause_due_ts=add_days(triggered_ts, SHOW_CAUSE_DUE_DAYS),
            alert_id=alert_id,
            triggers=list(triggers or []),
        )
        self._store[entity_id] = exam
        return exam

    def open_examination(self, entity_id: str) -> RfaExamination:
        exam = self._require(entity_id)
        validate_transition(RfaState(exam.state), RfaState.UNDER_EXAMINATION)
        exam.state = RfaState.UNDER_EXAMINATION.value
        return exam

    def record_show_cause_response(self, entity_id: str, *, response_ts: str) -> RfaExamination:
        """Record that the staffer responded to the show-cause notice (natural-justice gate)."""
        exam = self._require(entity_id)
        if exam.state != RfaState.UNDER_EXAMINATION.value:
            raise RfaTransitionError("show-cause response only valid during examination")
        exam.show_cause_response_ts = response_ts
        return exam

    def close(
        self, entity_id: str, *, outcome: str, now_ts: str
    ) -> RfaExamination:
        """Close the examination. ``outcome='confirmed'`` requires a recorded show-cause response
        (natural justice) and moves to CONFIRMED→CLOSED; ``outcome='exonerated'`` closes directly."""
        exam = self._require(entity_id)
        if outcome == "confirmed":
            if exam.show_cause_response_ts is None:
                raise RfaTransitionError(
                    "cannot confirm without a recorded show-cause response (natural justice)"
                )
            validate_transition(RfaState(exam.state), RfaState.CONFIRMED)
            exam.state = RfaState.CONFIRMED.value
        exam.outcome = outcome
        exam.state = RfaState.CLOSED.value
        exam.closed_ts = now_ts
        return exam

    # --- queries ---
    def get(self, entity_id: str) -> RfaExamination | None:
        return self._store.get(entity_id)

    def is_rfa_triggered(self, entity_id: str) -> bool:
        exam = self._store.get(entity_id)
        return bool(exam and exam.state != RfaState.CLOSED.value)

    def check_window_expiry(self, now_ts: str) -> list[RfaExamination]:
        """Open examinations past their 180-day clock — surfaced as a nudge (alert-only)."""
        return [
            e for e in self._store.values()
            if e.state not in (RfaState.CLOSED.value,) and e.window_expired(now_ts)
        ]

    def _require(self, entity_id: str) -> RfaExamination:
        exam = self._store.get(entity_id)
        if exam is None:
            raise RfaTransitionError(f"no RFA examination for {entity_id}")
        return exam

    # --- persistence seams (SCAFFOLD) ---
    def snapshot(self) -> list[dict]:
        return [e.to_dict() for e in self._store.values()]

    def reset(self) -> None:
        self._store.clear()


RFA_LIFECYCLE = RfaLifecycleService()
