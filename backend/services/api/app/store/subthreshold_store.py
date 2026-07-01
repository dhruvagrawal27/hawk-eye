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
    # A realistic funnel: ~1,000 scored, a handful alerted, the rest a sub-threshold long tail.
    demo = [
        ("EMP-2b14", 66, "off_hours_activity_rate_30d", "2026-06-30T01:12:00Z"),
        ("EMP-9f77", 63, "maker_checker_pair_frequency_30d", "2026-06-30T20:41:00Z"),
        ("EMP-3c55", 61, "db_rows_read_zscore_vs_peer", "2026-06-29T22:05:00Z"),
        ("EMP-7a21", 58, "export_volume_vs_baseline", "2026-06-30T02:47:00Z"),
        ("EMP-5d10", 57, "new_beneficiary_to_payment_latency_min", "2026-06-30T19:58:00Z"),
        ("EMP-8b93", 55, "privileged_session_off_hours", "2026-06-29T23:31:00Z"),
        ("EMP-1a09", 52, "amount_zscore_vs_peer", "2026-06-30T13:20:00Z"),
        ("EMP-4d99", 48, "failed_login_burst", "2026-06-30T09:05:00Z"),
        ("EMP-6e02", 44, "role_change_recency", "2026-06-28T16:44:00Z"),
        ("EMP-2b14", 59, "reversal_clustering_7d", "2026-06-30T18:02:00Z"),  # dedupes to max 66
    ]
    for entity, score, signal, ts in demo:
        SUBTHRESHOLD.observe(
            entity_id=entity, score=score, top_signal=signal, ts=ts, emitted=False
        )
    # Bulk long-tail so the funnel reads honestly (most scored activity is low-risk & unseen).
    for i in range(940):
        SUBTHRESHOLD.observe(
            entity_id=f"EMP-bg{i % 120:03d}",
            score=i % 40,  # 0–39, the low band
            top_signal="baseline",
            ts="2026-06-30T00:00:00Z",
            emitted=False,
        )
    SUBTHRESHOLD._alerted = 4  # the 4 seeded demo alerts that cleared the bar
    SUBTHRESHOLD._total_scored = SUBTHRESHOLD._total_scored + 4
