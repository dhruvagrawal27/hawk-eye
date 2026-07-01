"""Online feature reader (BACKEND reads; DATA owns).

# STUB: DATA (Feast/Redis online store). Reads online features by Feast keys for rule eval +
feature-vector assembly. The real reader calls Redis/Feast; this deterministic shim derives
features from the event plus a small short-term per-entity memory so the worked burst
(create_beneficiary → approve_payment) correlates exactly as DATA's stream would.

Contract (BACKEND.md §1/§6): features are a flat ``dict[str, value]`` keyed by feature name.
Caller may also embed precomputed features under ``event['features']`` — those are merged in.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# M1.2 — audit/config-tampering: decayed per-entity counter feeding AUDIT_CONFIG_TAMPERING.
_TAMPER_VERBS = ("audit_config_change", "disable_logging", "modify_audit", "clear_log")
_TAMPER_DECAY_HOURS = 24.0
_TAMPER_MAX_ENTITIES = 100  # bound the map so the stub cannot leak memory


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


class FeatureReader:
    """Per-entity online feature assembly (stub)."""

    def __init__(self) -> None:
        # beneficiary_id -> (creator_employee_id, created_ts)
        self._recent_beneficiaries: dict[str, tuple[str | None, datetime | None]] = {}
        # (maker, checker) pair -> count, to flag isolated pairs (L5 graph proxy in the fast path)
        self._pair_counts: dict[tuple[str, str], int] = {}
        # entity -> recent tampering-event timestamps (decayed window), for log_tampering_proxy
        self._tampering: dict[str, list[datetime]] = {}

    def _tampering_count(self, actor: str | None, verb: str, now: datetime | None) -> int | None:
        """Maintain a decayed (24h) per-entity tampering counter; bounded to avoid a leak."""
        if verb not in _TAMPER_VERBS or not actor or now is None:
            return None
        cutoff = now - timedelta(hours=_TAMPER_DECAY_HOURS)
        hist = self._tampering.setdefault(actor, [])
        hist[:] = [t for t in hist if t >= cutoff]
        hist.append(now)
        if len(self._tampering) > _TAMPER_MAX_ENTITIES:
            # evict the entity whose most-recent event is oldest (keep the current actor)
            oldest = min(self._tampering, key=lambda k: self._tampering[k][-1])
            if oldest != actor:
                self._tampering.pop(oldest, None)
        return len(hist)

    def observe(self, event: dict) -> None:
        """Update short-term memory from an event (the streaming windower's job in DATA)."""
        action = event.get("action") or {}
        obj = event.get("object") or {}
        actor = (event.get("actor") or {}).get("employee_id")
        verb = (action.get("verb") or "").lower()
        if verb in ("create_beneficiary", "add_beneficiary"):
            ben = obj.get("beneficiary_id")
            if ben:
                self._recent_beneficiaries[ben] = (actor, _parse_ts(event.get("ts")))

    def read(self, event: dict) -> dict:
        """Assemble the online feature view for one event."""
        features: dict = dict(event.get("features") or {})
        action = event.get("action") or {}
        obj = event.get("object") or {}
        context = event.get("context") or {}
        actor = (event.get("actor") or {}).get("employee_id")
        verb = (action.get("verb") or "").lower()
        now = _parse_ts(event.get("ts"))

        features.setdefault("is_off_hours", bool(context.get("is_off_hours")))

        # New-beneficiary correlation (fast-path feature for NEW_BENEFICIARY_THEN_HIGHVALUE + SoD).
        ben = obj.get("beneficiary_id")
        if ben and ben in self._recent_beneficiaries:
            creator, created_ts = self._recent_beneficiaries[ben]
            features.setdefault("beneficiary_created_by", creator)
            if now and created_ts:
                features.setdefault(
                    "minutes_since_new_beneficiary",
                    max(0.0, (now - created_ts).total_seconds() / 60.0),
                )
            if (
                creator
                and actor
                and creator == actor
                and "checker" in (action.get("maker_checker") or "")
            ):
                features.setdefault("maker_checker_same_actor", True)

        # Track maker-checker pairs to surface isolated-pair signals (graph proxy).
        if verb in ("approve_payment", "payment"):
            creator = features.get("beneficiary_created_by")
            if creator and actor and creator != actor:
                pair: tuple[str, str] = tuple(sorted((str(creator), str(actor))))  # type: ignore[assignment]
                self._pair_counts[pair] = self._pair_counts.get(pair, 0) + 1
                if self._pair_counts[pair] >= 2:
                    features.setdefault("maker_checker_pair_isolated", True)
                    features.setdefault("maker_checker_partner", creator)

        # Decayed audit/config-tampering counter (M1.2 → AUDIT_CONFIG_TAMPERING).
        tamper = self._tampering_count(actor, verb, now)
        if tamper is not None:
            features.setdefault("log_tampering_proxy", tamper)

        # After read, fold this event into memory for subsequent correlated events.
        self.observe(event)
        return features


FEATURE_READER = FeatureReader()
