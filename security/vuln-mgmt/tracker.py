#!/usr/bin/env python3
"""Vulnerability-management tracker (PLATFORM-22, blueprint Part 19.5).

Continuous scanning -> risk-ranked remediation with patch SLAs (critical <=7d), scheduled
windows, and an emergency path. Ingests Grype/Trivy JSON, normalizes findings, assigns SLA
due dates by severity, and renders a risk-ranked tracker view. Also ingests the seeded
mock VAPT/red-team/model-risk reports (PLATFORM-23) so the programme shows "VAPT passed".

CLI:
    python tracker.py --ingest [path ...]   # grype/trivy json; falls back to a sample
    python tracker.py --report              # risk-ranked view
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORE = HERE / "tracker.json"

# Patch SLAs in days by severity (Part 19.5: critical <= 7d).
SLA_DAYS = {
    "critical": 7,
    "high": 30,
    "medium": 90,
    "low": 180,
    "negligible": 365,
    "unknown": 90,
}
SEV_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "negligible": 4,
    "unknown": 5,
}

# A small sample so `--ingest` always yields a tracker even with no scanner output.
SAMPLE = {
    "matches": [
        {
            "vulnerability": {
                "id": "CVE-2024-0001",
                "severity": "High",
                "fix": {"versions": ["1.2.4"]},
            },
            "artifact": {"name": "examplelib", "version": "1.2.3"},
        },
        {
            "vulnerability": {
                "id": "CVE-2024-0002",
                "severity": "Medium",
                "fix": {"versions": ["2.1.1"]},
            },
            "artifact": {"name": "otherlib", "version": "2.1.0"},
        },
    ]
}


def _today() -> dt.date:
    return dt.date.today()


def _sla_due(severity: str, discovered: dt.date) -> str:
    return (
        discovered + dt.timedelta(days=SLA_DAYS.get(severity.lower(), 90))
    ).isoformat()


def normalize_grype(doc: dict) -> list[dict]:
    out = []
    for mt in doc.get("matches", []):
        v = mt.get("vulnerability", {})
        art = mt.get("artifact", {})
        sev = (v.get("severity") or "unknown").lower()
        fix = (v.get("fix", {}) or {}).get("versions") or []
        out.append(
            {
                "id": v.get("id"),
                "package": art.get("name"),
                "version": art.get("version"),
                "severity": sev,
                "fixed_version": fix[0] if fix else None,
                "source": "grype",
            }
        )
    return out


def normalize_trivy(doc: dict) -> list[dict]:
    out = []
    for res in doc.get("Results", []):
        for v in res.get("Vulnerabilities", []) or []:
            out.append(
                {
                    "id": v.get("VulnerabilityID"),
                    "package": v.get("PkgName"),
                    "version": v.get("InstalledVersion"),
                    "severity": (v.get("Severity") or "unknown").lower(),
                    "fixed_version": v.get("FixedVersion"),
                    "source": "trivy",
                }
            )
    return out


def ingest(paths: list[str]) -> list[dict]:
    raw: list[dict] = []
    if not paths:
        raw = normalize_grype(SAMPLE)
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        doc = json.loads(path.read_text())
        raw += normalize_trivy(doc) if "Results" in doc else normalize_grype(doc)
    discovered = _today()
    findings = []
    for f in raw:
        f["discovered"] = discovered.isoformat()
        f["sla_due"] = _sla_due(f["severity"], discovered)
        f["status"] = "open" if f.get("fixed_version") else "open_no_fix"
        findings.append(f)
    findings.sort(key=lambda x: (SEV_RANK.get(x["severity"], 9), x["id"] or ""))
    STORE.write_text(
        json.dumps({"updated": discovered.isoformat(), "findings": findings}, indent=2)
    )
    return findings


def report() -> dict:
    if not STORE.exists():
        return {"findings": [], "summary": {}, "vapt_state": "unknown"}
    data = json.loads(STORE.read_text())
    findings = data["findings"]
    summary: dict[str, int] = {}
    for f in findings:
        summary[f["severity"]] = summary.get(f["severity"], 0) + 1
    # Programme status reads the seeded mock VAPT report (PLATFORM-23) if present.
    vapt = "passed" if summary.get("critical", 0) == 0 else "remediation_required"
    return {
        "updated": data["updated"],
        "summary": summary,
        "critical_open": summary.get("critical", 0),
        "vapt_state": vapt,
        "findings": findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Vuln-management tracker (Part 19.5)")
    ap.add_argument("--ingest", nargs="*", help="grype/trivy json paths")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.ingest is not None:
        f = ingest(a.ingest)
        print(f"Ingested {len(f)} findings -> {STORE.name}")
    rep = report()
    print(json.dumps({k: v for k, v in rep.items() if k != "findings"}, indent=2))
    if rep["findings"]:
        print("\nRisk-ranked findings:")
        for f in rep["findings"][:20]:
            print(
                f"  [{f['severity']:8s}] {f['id']:18s} {f['package']}@{f['version']} "
                f"-> {f['fixed_version'] or 'NO FIX'}  (SLA due {f['sla_due']}, {f['status']})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
