"""Adversarial test battery harness (ML-27; blueprint Part 31 red-team).

Orchestrates the four robustness defenses as a single red-team battery so model-risk
reviews (Part 27) can run one call and get a pass/fail per attack class:

  * evasion             — an input crafted to evade one detector is caught by another.
  * poisoning           — a low-and-slow training-data drift is caught (change-point +
                          peer anchoring).
  * inversion           — raw scores never leak externally; extraction patterns flagged.
  * explanation         — a manipulated explanation contradicting rules/raw is flagged.

Each check is self-contained (constructs its own small adversarial scenario), so the
battery is callable with no external state. Returns a structured :class:`BatteryReport`.

ALERT-ONLY: the battery reports; it never blocks. Heavy ML members are OPTIONAL — the
default battery uses lightweight callable detectors so it runs anywhere without torch /
LightGBM in-process.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from ml.robustness.evasion import DiverseEnsembleDefense
from ml.robustness.explanation_defense import cross_check_explanation
from ml.robustness.inversion_defense import (
    ExtractionMonitor,
    InferenceDenied,
    InternalInferenceAPI,
)
from ml.robustness.poisoning import detect_low_and_slow_poisoning


@dataclass
class BatteryResult:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class BatteryReport:
    results: list[BatteryResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results) and bool(self.results)

    def to_dict(self) -> dict[str, Any]:
        return {"all_passed": self.all_passed, "results": [r.to_dict() for r in self.results]}


# --------------------------------------------------------------------------- #
# Default lightweight diverse ensemble (no torch / LightGBM needed)           #
# --------------------------------------------------------------------------- #
def default_diverse_ensemble(peer_groups: Optional[pd.Series] = None) -> DiverseEnsembleDefense:
    """A 4-signal ensemble (rule / unsupervised / supervised-proxy / graph-proxy).

    Each member keys off a DIFFERENT column so an input shaped to fool one is caught by
    another — this is the property the evasion test exercises.
    """
    def rule_member(X: pd.DataFrame) -> pd.Series:  # off-hours rate (rule signal)
        return X.get("offhours_rate", pd.Series(0.0, index=X.index)).clip(0, 1)

    def unsupervised_member(X: pd.DataFrame) -> pd.Series:  # amount outlier (density signal)
        a = pd.to_numeric(X.get("amount_max", pd.Series(0.0, index=X.index)), errors="coerce").fillna(0.0)
        hi = float(a.quantile(0.95)) or 1.0
        return (a / hi).clip(0, 1)

    def supervised_member(X: pd.DataFrame) -> pd.Series:  # learned proxy: new-bene + privilege
        bene = pd.to_numeric(X.get("n_create_beneficiary", pd.Series(0.0, index=X.index)), errors="coerce").fillna(0.0)
        return (bene / (bene.max() or 1.0)).clip(0, 1)

    def graph_member(X: pd.DataFrame) -> pd.Series:  # structural: export/exfil fan-out
        exp = pd.to_numeric(X.get("n_export", pd.Series(0.0, index=X.index)), errors="coerce").fillna(0.0)
        return (exp / (exp.max() or 1.0)).clip(0, 1)

    members: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
        "rules": rule_member,
        "unsupervised": unsupervised_member,
        "supervised": supervised_member,
        "graph": graph_member,
    }
    return DiverseEnsembleDefense(members, member_thresholds={k: 0.6 for k in members},
                                  peer_groups=peer_groups, secret="battery-fixed-secret")


# --------------------------------------------------------------------------- #
# Individual battery checks                                                    #
# --------------------------------------------------------------------------- #
def _check_evasion() -> BatteryResult:
    # Build a population; craft an evader that zeroes the supervised signal (no new
    # beneficiaries) but exfiltrates -> the graph member must still catch it.
    idx = [f"EMP-{i:03d}" for i in range(20)]
    rng = np.random.default_rng(0)
    X = pd.DataFrame({
        "offhours_rate": rng.uniform(0, 0.2, 20),
        "amount_max": rng.uniform(1e3, 5e4, 20),
        "n_create_beneficiary": rng.integers(0, 1, 20).astype(float),
        "n_export": np.zeros(20),
    }, index=idx)
    evader = "EMP-019"
    X.loc[evader, ["offhours_rate", "amount_max", "n_create_beneficiary"]] = [0.05, 2e4, 0.0]
    X.loc[evader, "n_export"] = 50.0  # heavy exfil -> graph signal saturates

    ens = default_diverse_ensemble()
    v = ens.evaluate_one(X, evader)
    # Supervised member must NOT fire (successfully evaded), graph member MUST fire.
    evaded_supervised = "supervised" not in v.detectors_fired
    caught_by_graph = "graph" in v.detectors_fired
    passed = evaded_supervised and caught_by_graph and v.flagged
    return BatteryResult("evasion", passed,
                         f"fired={v.detectors_fired} (evaded supervised, caught by graph)")


def _check_poisoning() -> BatteryResult:
    # Low-and-slow: entity ramps from 0.1 -> 0.9 over the window; peers stay flat.
    n = 24
    entity = np.concatenate([np.full(n // 2, 0.1), np.linspace(0.1, 0.9, n - n // 2)])
    peers = {f"PEER-{j}": np.full(n, 0.1) + np.random.default_rng(j).normal(0, 0.01, n) for j in range(6)}
    rep = detect_low_and_slow_poisoning(entity, peers, entity_id="EMP-poison", drift_thresh=0.1)
    return BatteryResult("poisoning", rep.poisoning_suspected, rep.detail)


def _check_inversion() -> BatteryResult:
    api = InternalInferenceAPI(
        lambda f: float(np.clip(np.mean(f), 0, 1)),
        authorized_tokens={"ext-tok": "external", "int-tok": "internal"},
        model_version="m@1", max_calls=5, per_seconds=60.0,
        extraction_monitor=ExtractionMonitor(max_queries=3, window_seconds=60.0),
    )
    feats = [0.9, 0.9]
    # External caller gets a band, never a raw float.
    banded = api.infer(feats, token="ext-tok", principal="ext", raw=False, now=1000.0)
    external_never_raw = hasattr(banded, "band") and not isinstance(banded, float)
    # External raw request is refused.
    try:
        api.infer(feats, token="ext-tok", principal="ext", raw=True, now=1000.0)
        raw_blocked = False
    except InferenceDenied:
        raw_blocked = True
    # Rate limiting fires under a burst.
    rate_limited = False
    for t in range(10):
        try:
            api.infer(feats, token="ext-tok", principal="burst", raw=False, now=1000.0 + t * 0.01)
        except InferenceDenied:
            rate_limited = True
            break
    # Extraction pattern (repeated identical probing) flagged.
    mon_api = InternalInferenceAPI(
        lambda f: 0.5, authorized_tokens={"t": "external"}, max_calls=1000,
        extraction_monitor=ExtractionMonitor(max_queries=4, window_seconds=60.0, dup_ratio_thresh=0.5),
    )
    for t in range(12):
        mon_api.infer([0.1, 0.2, 0.3], token="t", principal="harvester", now=2000.0 + t)
    extraction_flagged = len(mon_api.extraction_flags()) > 0
    passed = external_never_raw and raw_blocked and rate_limited and extraction_flagged
    return BatteryResult("inversion", passed,
                         f"external_banded={external_never_raw} raw_blocked={raw_blocked} "
                         f"rate_limited={rate_limited} extraction_flagged={extraction_flagged}")


def _check_explanation() -> BatteryResult:
    # A manipulated explanation blames a benign feature (with no raw support) while the
    # real fired rule (new_beneficiary_high_value) is omitted.
    manipulated = [
        {"source": "shap", "feature": "tenure_days", "contribution": 0.9},
        {"source": "shap", "feature": "login_velocity_60m", "contribution": 0.1},
    ]
    check = cross_check_explanation(
        manipulated,
        fired_rules=["new_beneficiary_high_value", "off_hours"],
        raw_evidence={"new_beneficiary_high_value": 1.0, "off_hours": 1.0,
                      "tenure_days": 0.0, "login_velocity_60m": 0.0},
    )
    return BatteryResult("explanation", check.flagged, check.detail)


def run_adversarial_battery() -> BatteryReport:
    """Run all four robustness checks and return a structured report."""
    return BatteryReport(results=[
        _check_evasion(),
        _check_poisoning(),
        _check_inversion(),
        _check_explanation(),
    ])
