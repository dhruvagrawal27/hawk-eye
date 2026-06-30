"""Online feature reader (BACKEND reads; DATA owns).

# STUB: DATA (Feast/Redis online store). Reads online features by Feast keys for rule eval +
feature-vector assembly. The real reader calls Redis/Feast; this deterministic shim derives
features from the event plus a small short-term per-entity memory so the worked burst
(create_beneficiary → approve_payment) correlates exactly as DATA's stream would.

Contract (BACKEND.md §1/§6): features are a flat ``dict[str, value]`` keyed by feature name.
Caller may also embed precomputed features under ``event['features']`` — those are merged in.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


class FeatureReader:
    """Per-entity online feature assembly (stub)."""

    def __init__(self) -> None:
        # beneficiary_id -> (creator_employee_id, created_ts)
        self._recent_beneficiaries: dict[str, tuple[str, datetime | None]] = {}
        # (maker, checker) pair -> count, to flag isolated pairs (L5 graph proxy in the fast path)
        self._pair_counts: dict[tuple[str, str], int] = {}

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
            if creator and actor and creator == actor and "checker" in (action.get("maker_checker") or ""):
                features.setdefault("maker_checker_same_actor", True)

        # Track maker-checker pairs to surface isolated-pair signals (graph proxy).
        if verb in ("approve_payment", "payment"):
            creator = features.get("beneficiary_created_by")
            if creator and actor and creator != actor:
                pair = tuple(sorted((creator, actor)))  # type: ignore[arg-type]
                self._pair_counts[pair] = self._pair_counts.get(pair, 0) + 1
                if self._pair_counts[pair] >= 2:
                    features.setdefault("maker_checker_pair_isolated", True)
                    features.setdefault("maker_checker_partner", creator)

        # After read, fold this event into memory for subsequent correlated events.
        self.observe(event)
        return features


FEATURE_READER = FeatureReader()
