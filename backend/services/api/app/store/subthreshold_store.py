"""Sub-threshold (ambient) activity store — the 'hidden 95%'.

Every event runs the full detector stack, but only fused scores ≥ EMIT_THRESHOLD (70) surface as
alerts; everything below is scored-then-dropped (recorded to ClickHouse, never shown). That silent
majority *is* signal — near-misses, slow-drift actors sitting at 55–69, the population the analyst
never sees. This in-memory store captures those sub-threshold observations so the UI can show the
**detection funnel** (scored → sub-threshold → alerted) and a **watchlist** of elevated-but-not-
alerted entities. Pure: no DB, no network (mirrors the ClickHouse `hawkeye.scores` sub-70 rows).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

# Sub-threshold bands under the 70 emit line (ordered high→low). `watch` (55–69) is the "almost
# alerted" population that matters most; `elevated` (40–54) is worth a periodic sweep.
BANDS: tuple[tuple[str, int, int], ...] = (
    ("watch", 55, 70),
    ("elevated", 40, 55),
    ("low", 0, 40),
)


@dataclass
class SubThresholdObs:
    entity_id: str
    score: int
    top_signal: str
    ts: str


def _band_for(score: int) -> str:
    for label, lo, hi in BANDS:
        if lo <= score < hi:
            return label
    return "low"


class SubThresholdStore:
    def __init__(self, maxlen: int = 1000) -> None:
        self._obs: deque[SubThresholdObs] = deque(maxlen=maxlen)
        self._total_scored = 0
        self._alerted = 0
        self._band_counts: dict[str, int] = {label: 0 for label, _, _ in BANDS}

    def reset(self) -> None:
        self._obs.clear()
        self._total_scored = 0
        self._alerted = 0
        self._band_counts = {label: 0 for label, _, _ in BANDS}

    def observe(
        self, *, entity_id: str, score: int, top_signal: str, ts: str, emitted: bool
    ) -> None:
        """Record one fully-scored event. `emitted` = it cleared the bar and became an alert."""
        self._total_scored += 1
        if emitted:
            self._alerted += 1
            return
        self._band_counts[_band_for(score)] += 1
        if score >= 40:  # keep the interesting (elevated/watch) ones on the watchlist ring
            self._obs.append(
                SubThresholdObs(entity_id=entity_id, score=int(score), top_signal=top_signal, ts=ts)
            )

    def watchlist(self, limit: int = 20) -> list[SubThresholdObs]:
        """Highest-scoring sub-threshold observation per entity, ranked desc (near-misses first)."""
        best: dict[str, SubThresholdObs] = {}
        for o in self._obs:
            cur = best.get(o.entity_id)
            if cur is None or o.score > cur.score:
                best[o.entity_id] = o
        return sorted(best.values(), key=lambda o: o.score, reverse=True)[:limit]

    def snapshot(self, watch_limit: int = 20) -> dict:
        sub_total = sum(self._band_counts.values())
        return {
            "total_scored": self._total_scored,
            "alerted": self._alerted,
            "sub_threshold": sub_total,
            "emit_threshold": 70,
            "bands": [
                {"label": label, "min": lo, "max": hi, "count": self._band_counts[label]}
                for label, lo, hi in BANDS
            ],
            "watchlist": [
                {
                    "entity_id": o.entity_id,
                    "score": o.score,
                    "top_signal": o.top_signal,
                    "ts": o.ts,
                }
                for o in self.watchlist(watch_limit)
            ],
        }


SUBTHRESHOLD = SubThresholdStore()


def seed_subthreshold() -> None:
    """Idempotent demo seed: a plausible ambient population so the funnel + watchlist are never empty
    (the live pipeline also records into this store as events flow). Synthetic, honest."""
    SUBTHRESHOLD.reset()
    # A realistic near-miss watchlist — one privileged actor per row, real signal, score 46–69.
    # These populate the watchlist (ranked desc, deduped per entity) and a little of the mid bands.
    demo = [
        ("EMP-2b14", 67, "off_hours_activity_rate_30d", "2026-06-30T01:12:00Z"),
        ("EMP-9f77", 65, "maker_checker_pair_frequency_30d", "2026-06-30T20:41:00Z"),
        ("EMP-3c55", 64, "db_rows_read_zscore_vs_peer", "2026-06-29T22:05:00Z"),
        ("EMP-7a21", 62, "export_volume_vs_baseline", "2026-06-30T02:47:00Z"),
        ("EMP-5d10", 61, "new_beneficiary_to_payment_latency_min", "2026-06-30T19:58:00Z"),
        ("EMP-8b93", 60, "privileged_session_off_hours", "2026-06-29T23:31:00Z"),
        ("EMP-2c31", 59, "swift_message_without_cbs_recon", "2026-06-30T21:10:00Z"),
        ("EMP-1a09", 58, "amount_zscore_vs_peer", "2026-06-30T13:20:00Z"),
        ("EMP-4f88", 57, "entitlement_change_velocity", "2026-06-30T11:02:00Z"),
        ("EMP-6e02", 55, "dormant_account_reactivation", "2026-06-28T16:44:00Z"),
        ("EMP-3d77", 53, "vendor_bank_detail_overlap", "2026-06-30T10:15:00Z"),
        ("EMP-9b40", 51, "standing_privilege_unused", "2026-06-29T14:33:00Z"),
        ("EMP-7c19", 49, "reversal_clustering_7d", "2026-06-30T18:02:00Z"),
        ("EMP-4d99", 48, "failed_login_burst", "2026-06-30T09:05:00Z"),
        ("EMP-5a62", 46, "role_change_recency", "2026-06-27T16:44:00Z"),
        ("EMP-8f03", 45, "geo_velocity_impossible", "2026-06-30T07:20:00Z"),
    ]
    for entity, score, signal, ts in demo:
        SUBTHRESHOLD.observe(
            entity_id=entity, score=score, top_signal=signal, ts=ts, emitted=False
        )
    # Scale the funnel to a realistic bank-week (~52k privileged actions screened) WITHOUT looping
    # tens of thousands of times (keeps the test reseed fast): set the band totals + counters
    # directly. The watchlist ring above stays the curated near-miss set. Arithmetic stays
    # self-consistent: total_scored == alerted + sub_threshold, sub_threshold == sum(bands).
    SUBTHRESHOLD._band_counts["watch"] = 214  # 55–69, "almost alerted"
    SUBTHRESHOLD._band_counts["elevated"] = 486  # 40–54, worth a periodic sweep
    SUBTHRESHOLD._band_counts["low"] = 51_300  # 0–39, the benign majority
    alerted = 420  # ~ the alerts that cleared the 70 bar this week
    SUBTHRESHOLD._alerted = alerted
    SUBTHRESHOLD._total_scored = alerted + sum(SUBTHRESHOLD._band_counts.values())
