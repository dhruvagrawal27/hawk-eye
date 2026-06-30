#!/usr/bin/env python3
"""Independent-validation sign-off gate (PLATFORM-34, blueprint Part 27.2 / Part 22.4).

Blocks promotion of a model version "to Production" until a **simulated independent
validation sign-off** exists in the governance DB (a function SEPARATE from the
developers — the SR 11-7 "effective challenge"). MOCK: the sign-off RECORD is seeded;
the real act needs a real independent validator.

Used by the CD pipeline / `POST /models/{id}/promote` path as a gate. Exit 0 = allowed,
exit 3 = blocked.

Usage:
    python signoff_gate.py --model-version fusion-2026.2.0          # check
    python signoff_gate.py --model-version unknown-9.9.9            # blocks
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))
import models as m  # noqa: E402


def check(model_version: str) -> dict:
    s = m.get_session()
    validation = (
        s.query(m.ModelValidation)
        .filter_by(model_version=model_version, signoff_status="signed_off")
        .first()
    )
    promotion = (
        s.query(m.Approval)
        .filter_by(
            model_version=model_version,
            artifact_type="model_promotion",
            decision="approved",
        )
        .first()
    )
    allowed = validation is not None and promotion is not None
    reasons = []
    if validation is None:
        reasons.append("no signed-off independent model-validation record (Part 27.2)")
    if promotion is None:
        reasons.append("no AI/Model-Risk Committee promotion approval (Part 22.4)")
    return {
        "model_version": model_version,
        "allowed": allowed,
        "validator": validation.validator if validation else None,
        "promotion_resolution": promotion.resolution_id if promotion else None,
        "reasons": reasons or ["independent validation signed off; promotion approved"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Independent-validation sign-off gate (PLATFORM-34)"
    )
    ap.add_argument("--model-version", required=True)
    a = ap.parse_args()
    r = check(a.model_version)
    verdict = (
        "ALLOW promotion to Production"
        if r["allowed"]
        else "BLOCK promotion to Production"
    )
    print(f"[signoff-gate] {a.model_version}: {verdict}")
    for reason in r["reasons"]:
        print(f"   - {reason}")
    return 0 if r["allowed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
