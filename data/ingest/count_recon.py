"""Count reconciliation: ingested vs source-of-truth to detect silent feed loss (DATA-17).

Blueprint Part 32.2 (l.1306): "periodically reconcile ingested counts vs source-of-truth
to detect silent feed loss (a missing feed = a blind spot a fraudster could exploit)."

Status: REAL pure-python (pandas optional for the report; falls back to dicts).
Deterministic. A drop below a tolerance threshold for any source raises a mismatch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


@dataclass
class ReconResult:
    source: str
    source_of_truth: int
    ingested: int
    tolerance: float                 # allowed fractional shortfall, e.g. 0.0
    @property
    def delta(self) -> int:
        return self.ingested - self.source_of_truth

    @property
    def shortfall_fraction(self) -> float:
        if self.source_of_truth == 0:
            return 0.0
        return max(0, self.source_of_truth - self.ingested) / self.source_of_truth

    @property
    def ok(self) -> bool:
        return self.shortfall_fraction <= self.tolerance

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "source_of_truth": self.source_of_truth,
                "ingested": self.ingested, "delta": self.delta,
                "shortfall_fraction": round(self.shortfall_fraction, 6),
                "ok": self.ok, "status": "OK" if self.ok else "FEED_LOSS"}


@dataclass
class CountReconciler:
    """Track per-source ingested counts and reconcile against source-of-truth counts."""
    tolerance: float = 0.0
    _ingested: dict[str, int] = field(default_factory=dict)

    def record(self, source: str, n: int = 1) -> None:
        self._ingested[source] = self._ingested.get(source, 0) + n

    def record_event(self, ev: dict) -> None:
        """Count one L0 event by its source channel (action.channel)."""
        src = (ev.get("action") or {}).get("channel") or "unknown"
        self.record(src)

    def reconcile(self, source_of_truth: dict[str, int]) -> list[ReconResult]:
        """Compare ingested vs source-of-truth for every known source."""
        results: list[ReconResult] = []
        sources = set(source_of_truth) | set(self._ingested)
        for src in sorted(sources):
            results.append(ReconResult(
                source=src,
                source_of_truth=int(source_of_truth.get(src, 0)),
                ingested=int(self._ingested.get(src, 0)),
                tolerance=self.tolerance,
            ))
        return results

    def feed_loss(self, source_of_truth: dict[str, int]) -> list[ReconResult]:
        """Only the sources where a silent feed loss was detected."""
        return [r for r in self.reconcile(source_of_truth) if not r.ok]


def reconcile_counts(
    ingested_events: Iterable[dict],
    source_of_truth: dict[str, int],
    tolerance: float = 0.0,
) -> list[ReconResult]:
    """One-shot helper: count events by channel and reconcile vs source-of-truth."""
    rec = CountReconciler(tolerance=tolerance)
    for ev in ingested_events:
        rec.record_event(ev)
    return rec.reconcile(source_of_truth)


def to_frame(results: list[ReconResult]) -> Any:
    """Optional pandas DataFrame of recon results (falls back to a list of dicts)."""
    rows = [r.to_dict() for r in results]
    try:
        import pandas as pd

        return pd.DataFrame(rows)
    except Exception:
        return rows
