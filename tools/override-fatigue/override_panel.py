#!/usr/bin/env python3
"""Override-rate (trust calibration) + alert-fatigue panel (PLATFORM-39, Part 33.4).

Computes the two adoption metrics that matter most operationally — REAL, from disposition/
feedback data — and writes them to the governance DB `operating_metrics` (surfaced in the
dashboard governance/ops view, and as the change-mgmt panel):
  - override_rate  : fraction of AI 'fraud' classifications a human OVERRODE (false_positive).
                     Too high => analysts don't trust the model (mis-calibration / too noisy).
  - alert_fatigue  : fraction of dispositions handled in < a rushed-threshold time
                     (proxy for fatigue; the #1 operational failure mode, Part 14/19).

`python override_panel.py` (uses a synthetic disposition sample) or import compute().
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "governance" / "db"))

RUSHED_MIN = 3.0   # dispositions faster than this look rushed (fatigue proxy)

# Synthetic disposition feed (real source: hawkeye.feedback / BACKEND disposition events).
SAMPLE = [
    {"ai": "fraud", "human": "fraud", "analyst": "a1", "mins": 22},
    {"ai": "fraud", "human": "false_positive", "analyst": "a1", "mins": 2},
    {"ai": "fraud", "human": "fraud", "analyst": "a2", "mins": 18},
    {"ai": "fraud", "human": "false_positive", "analyst": "a2", "mins": 1.5},
    {"ai": "fraud", "human": "inconclusive", "analyst": "a3", "mins": 30},
    {"ai": "fraud", "human": "fraud", "analyst": "a3", "mins": 25},
    {"ai": "benign", "human": "false_positive", "analyst": "a1", "mins": 5},
    {"ai": "fraud", "human": "fraud", "analyst": "a2", "mins": 12},
]


def compute(dispositions: list[dict]) -> dict:
    ai_fraud = [d for d in dispositions if d["ai"] == "fraud"]
    overridden = [d for d in ai_fraud if d["human"] == "false_positive"]
    override_rate = round(len(overridden) / len(ai_fraud), 4) if ai_fraud else 0.0
    rushed = [d for d in dispositions if d["mins"] < RUSHED_MIN]
    alert_fatigue = round(len(rushed) / len(dispositions), 4) if dispositions else 0.0
    return {"override_rate": override_rate, "alert_fatigue": alert_fatigue,
            "n_dispositions": len(dispositions), "n_ai_fraud": len(ai_fraud)}


def write_metrics(metrics: dict, period: str = "live") -> None:
    import models as m
    s = m.get_session()
    for name in ("override_rate", "alert_fatigue"):
        s.add(m.OperatingMetric(metric=name, value=metrics[name], period=period))
    s.commit()


def main() -> int:
    metrics = compute(SAMPLE)
    print("Override-rate / Alert-fatigue panel (PLATFORM-39, Part 33.4):")
    print(f"  override_rate : {metrics['override_rate']:.0%}  "
          f"({'OK' if metrics['override_rate'] <= 0.30 else 'HIGH — review model calibration'})")
    print(f"  alert_fatigue : {metrics['alert_fatigue']:.0%}  "
          f"({'OK' if metrics['alert_fatigue'] <= 0.40 else 'HIGH — tune thresholds / staffing'})")
    print(f"  over {metrics['n_dispositions']} dispositions ({metrics['n_ai_fraud']} AI-fraud)")
    try:
        write_metrics(metrics)
        print("  -> written to governance DB operating_metrics (surfaced in dashboard)")
    except Exception as e:
        print(f"  (governance DB not available: {e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
