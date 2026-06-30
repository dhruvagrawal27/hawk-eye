"""Operational and business metrics for Hawk-Eye (ML-29).

Blueprint Part 14 splits metrics into three families:

* **Detection** — PR-AUC/AP, precision@k, alert-to-true ratio, recall, TTD.
  Those live in :mod:`ml.eval.metrics` (the honest-eval harness) and are NOT
  re-implemented here.
* **Operational** — alert volume vs analyst capacity, mean-time-to-detection /
  mean-time-to-disposition, false-positive rate, RBI <=30-day TAT compliance.
* **Business** — estimated loss avoided, cases surfaced by system vs tips.

This package owns the operational + business families. Every function is a
pure function with explicit inputs (no global state, no I/O) so it can be unit
tested on toy cases and reused by dashboards, governance reports, and the
MRM review pack.
"""

from __future__ import annotations

from ml.metrics.ops import (
    OpsDashboard,
    alert_volume_vs_capacity,
    cases_surfaced_system_vs_tips,
    compute_ops_dashboard,
    estimated_loss_avoided,
    false_positive_rate,
    mean_time_to_detection,
    mean_time_to_disposition,
    rbi_tat_compliance,
)

__all__ = [
    "OpsDashboard",
    "alert_volume_vs_capacity",
    "mean_time_to_detection",
    "mean_time_to_disposition",
    "false_positive_rate",
    "rbi_tat_compliance",
    "estimated_loss_avoided",
    "cases_surfaced_system_vs_tips",
    "compute_ops_dashboard",
]
