"""SWIFT<->CBS reconciliation join — the PNB control (DATA-16).

Blueprint Part 32.1 (l.1294, the SWIFT<->CBS reconciliation join), Part 6.2 (l.232,
"SWIFT<->CBS reconciliation mismatch — instrument with no CBS entry"), and the
Part 21.1 SWIFT-without-CBS typology (l.800).

Status: REAL on synthetic data. Joins SWIFT/instrument message events to CBS posting
events on the linkage correlation keys (swift_ref/cbs_ref) and emits a
`recon_mismatch` signal onto Topics.EVENTS_SIGNALS for every instrument message with
NO matching CBS posting (the PNB mechanism). It fires on the injected SWIFT-without-CBS
fraud and stays quiet on matched pairs. BACKEND's L1 turns this signal into a rule hit.

Determinism: pure join logic; no randomness.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from data.config import Topics, make_id
from data.eventbus import InProcessBus

RECON_SIGNAL = "recon_mismatch"


def _is_swift(ev: dict) -> bool:
    action = ev.get("action") or {}
    chan = (action.get("channel") or "").lower()
    return chan == "swift" or (ev.get("linkage") or {}).get("swift_ref") is not None


def _is_cbs(ev: dict) -> bool:
    action = ev.get("action") or {}
    chan = (action.get("channel") or "").lower()
    return chan == "cbs" or (ev.get("linkage") or {}).get("cbs_ref") is not None


def _ref(ev: dict) -> Optional[str]:
    """The correlation ref that should link a SWIFT instrument to its CBS posting.

    Both sides carry the SAME logical reference: the SWIFT side stamps it on
    linkage.swift_ref, the CBS posting side stamps the matching value on
    linkage.cbs_ref. A genuine pair shares one value across the two fields.
    """
    link = ev.get("linkage") or {}
    return link.get("swift_ref") or link.get("cbs_ref")


def _signal_event(swift_ev: dict, ref: Optional[str]) -> dict[str, Any]:
    """Build a recon_mismatch signal event (L0-shaped, keyed by the SWIFT actor)."""
    actor = swift_ev.get("actor") or {}
    obj = swift_ev.get("object") or {}
    emp = actor.get("employee_id", "")
    sig_id = make_id("event", "recon", swift_ev.get("event_id", ""), ref or "")
    return {
        "event_id": sig_id,
        "ts": swift_ev.get("ts"),
        "signal": RECON_SIGNAL,
        "actor": {"employee_id": emp, "role": actor.get("role"),
                  "branch": actor.get("branch")},
        "action": {"verb": "recon_mismatch", "channel": "recon"},
        "object": {"instrument": obj.get("instrument"), "amount": obj.get("amount"),
                   "currency": obj.get("currency")},
        "context": {"ts": swift_ev.get("ts"),
                    "is_off_hours": (swift_ev.get("context") or {}).get("is_off_hours")},
        "linkage": {"swift_ref": ref, "cbs_ref": None,
                    "source_event_id": swift_ev.get("event_id")},
        "reason": "swift_without_cbs",
    }


class SwiftCbsReconciler:
    """Stateful reconciler: buffer CBS refs, emit a mismatch for unmatched SWIFT msgs."""

    def __init__(self, bus: Optional[InProcessBus] = None,
                 topic: str = Topics.EVENTS_SIGNALS) -> None:
        self.bus = bus
        self.topic = topic
        self._cbs_refs: set[str] = set()
        self._pending_swift: dict[str, dict] = {}   # ref -> swift event awaiting CBS
        self.emitted: list[dict] = []

    def _emit(self, swift_ev: dict, ref: Optional[str]) -> None:
        sig = _signal_event(swift_ev, ref)
        self.emitted.append(sig)
        if self.bus is not None:
            self.bus.publish(self.topic, sig)

    def observe(self, ev: dict) -> None:
        """Feed one L0 event. CBS postings clear matching pending SWIFT messages."""
        ref = _ref(ev)
        if _is_cbs(ev):
            if ref:
                self._cbs_refs.add(ref)
                self._pending_swift.pop(ref, None)  # matched -> stays quiet
            return
        if _is_swift(ev):
            if ref and ref in self._cbs_refs:
                return                                # already matched
            # unmatched so far; hold until end-of-batch flush
            self._pending_swift[ref or ev.get("event_id", "")] = ev

    def flush(self) -> list[dict]:
        """Emit a recon_mismatch for every SWIFT message still without a CBS posting."""
        for ref, swift_ev in list(self._pending_swift.items()):
            if ref in self._cbs_refs:
                continue
            self._emit(swift_ev, _ref(swift_ev))
        self._pending_swift.clear()
        return self.emitted


def reconcile(
    events: Iterable[dict],
    bus: Optional[InProcessBus] = None,
    topic: str = Topics.EVENTS_SIGNALS,
) -> list[dict]:
    """Batch helper: reconcile a stream of L0 events, return emitted mismatch signals.

    Fires on instrument messages with no matching CBS posting; quiet on matched pairs.
    """
    rec = SwiftCbsReconciler(bus=bus, topic=topic)
    for ev in events:
        rec.observe(ev)
    return rec.flush()
