#!/usr/bin/env python3
"""DB-backed go-live readiness checklist (PLATFORM-41, blueprint Part 34.6 + 34.5).

Reads each go_live_tick from the governance DB, resolves its status by checking the
referenced evidence record exists (and is approved/passed), then renders ONE go/no-go
gate across all Part 34.6 categories. Also emits the **threat-intel feedback-loop**
hand-off note (Part 34.5) routing new typologies back to BACKEND/DATA.

`make go-live`. Reads SQLite (default) or Postgres (GOVERNANCE_DB_URL). Run
`make seed-governance` first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))
import models as m  # noqa: E402

CATEGORY_ORDER = [
    "regulatory",
    "security",
    "reliability",
    "quality",
    "data",
    "operating_model",
    "program",
]


def _parse_filter(flt: str | None) -> dict:
    out: dict[str, str] = {}
    for part in (flt or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _coerce(value: str):
    if value.isdigit():
        return int(value)
    return value


def resolve(session) -> list[dict]:
    ticks = session.query(m.GoLiveTick).all()
    results = []
    for t in ticks:
        model = m.TABLE_MODELS.get(t.evidence_table or "")
        met = False
        evidence_ref = None
        if model is not None:
            filt = {k: _coerce(v) for k, v in _parse_filter(t.evidence_filter).items()}
            try:
                row = session.query(model).filter_by(**filt).first()
            except Exception:
                row = None
            if row is not None:
                met = True
                evidence_ref = f"{t.evidence_table}#{row.id}"
        t.status = "met" if met else "not_met"
        t.evidence_ref = evidence_ref
        results.append(
            {
                "category": t.category,
                "item": t.item,
                "status": t.status,
                "evidence": evidence_ref,
            }
        )
    session.commit()
    return results


def threat_intel_handoff() -> dict:
    """Part 34.5: route new typologies back into rules + the synthetic library."""
    return {
        "new_typologies": [
            "instant-payment mule fan-out (UPI)",
            "vendor-bank-detail swap before disbursement",
        ],
        "routes_to": {
            "BACKEND": "add L1 rules (BRE/SoD matrix) for the new typologies",
            "DATA": "add scenarios to the synthetic red-team library (DATA simulator)",
        },
        "cadence": "fed from red-team exercises + external fraud-typology intel (Part 19/34.5)",
        "note": "HAND-OFF: PLATFORM raises; BACKEND + DATA implement (alert-only preserved).",
    }


def render(results: list[dict], handoff: dict) -> dict:
    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)
    total = len(results)
    met = sum(1 for r in results if r["status"] == "met")
    gate = "GO" if met == total else "NO-GO"
    return {
        "gate": gate,
        "met": met,
        "total": total,
        "by_category": by_cat,
        "threat_intel_feedback": handoff,
    }


def main() -> int:
    as_json = "--json" in sys.argv
    s = m.get_session()
    if s.query(m.GoLiveTick).count() == 0:
        print("No go-live ticks. Run `make seed-governance` first.", file=sys.stderr)
        return 2
    summary = render(resolve(s), threat_intel_handoff())

    if as_json:
        print(json.dumps(summary, indent=2))
        return 0

    print("=" * 64)
    print("  HAWK-EYE — GO-LIVE READINESS CHECKLIST (Part 34.6)")
    print("=" * 64)
    for cat in CATEGORY_ORDER + [
        c for c in summary["by_category"] if c not in CATEGORY_ORDER
    ]:
        items = summary["by_category"].get(cat)
        if not items:
            continue
        print(f"\n[{cat.upper()}]")
        for r in items:
            mark = "✓" if r["status"] == "met" else "✗"
            ev = f"  ({r['evidence']})" if r["evidence"] else ""
            print(f"  {mark} {r['item']}{ev}")
    print("\n" + "-" * 64)
    print(f"  Evidence met: {summary['met']}/{summary['total']}")
    print(f"  >>> GATE: {summary['gate']} <<<")
    print("-" * 64)
    print("\nThreat-intel feedback loop (Part 34.5) -> hand-off to:")
    for ws, action in summary["threat_intel_feedback"]["routes_to"].items():
        print(f"  [{ws}] {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
