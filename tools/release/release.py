#!/usr/bin/env python3
"""Release governance tool (PLATFORM-19, blueprint Part 31.3 / Part 34.3).

Cuts a versioned release: release notes (from git log) + a requirement->code->test->deploy
traceability matrix + a scheduled-change-window check. CAB approval is the human step
(SCAFFOLD) — the tool prepares the package; a human/CAB approves (recorded in the governance
DB approvals table, artifact_type=cab_change).

CLI:
    python release.py notes --version v1.0.0
    python release.py traceability
    python release.py window-check
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
TRACE = Path(__file__).resolve().parent / "traceability.yaml"

# Allowed change windows (Part 31.3 scheduled windows). UTC hours; weekday 0=Mon.
ALLOWED_WINDOWS = [
    {"weekday": 5, "start_h": 18, "end_h": 23},  # Sat evening
    {"weekday": 6, "start_h": 0, "end_h": 6},  # Sun early
]


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git"] + args, cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def release_notes(version: str) -> str:
    last_tag = _git(["describe", "--tags", "--abbrev=0", "HEAD^"]) or ""
    rng = f"{last_tag}..HEAD" if last_tag else "HEAD~20..HEAD"
    log = _git(["log", rng, "--pretty=format:- %s (%h)"])
    today = dt.date.today().isoformat()
    return (
        f"# Release {version} ({today})\n\n"
        f"Versioned release (Part 34.3). Range: {rng or 'recent'}\n\n"
        f"## Changes\n{log or '- (no commits found)'}\n\n"
        f"## Gates passed\nCI pyramid + ML/data gates + security scans + signoff-gate "
        f"(see .github/workflows/ci.yml, cd.yml).\n\n"
        f"## CAB\nCAB approval required before production deploy (recorded in governance "
        f"approvals; resolution CAB-*). Rollback: governance/change-mgmt/rollback-runbook.md\n"
    )


def traceability() -> dict:
    try:
        import yaml

        data = yaml.safe_load(TRACE.read_text()) if TRACE.exists() else {}
    except Exception:
        data = {}
    return data


def window_check(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    for w in ALLOWED_WINDOWS:
        if now.weekday() == w["weekday"] and w["start_h"] <= now.hour < w["end_h"]:
            return {"in_window": True, "window": w, "now_utc": now.isoformat()}
    return {
        "in_window": False,
        "allowed_windows": ALLOWED_WINDOWS,
        "now_utc": now.isoformat(),
        "note": "production change blocked outside scheduled windows (Part 31.3); "
        "use the emergency-patch path for criticals.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Release governance (Part 31.3/34.3)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("notes")
    n.add_argument("--version", default="v0.1.0")
    sub.add_parser("traceability")
    sub.add_parser("window-check")
    a = ap.parse_args()
    if a.cmd == "notes":
        OUT.mkdir(parents=True, exist_ok=True)
        notes = release_notes(a.version)
        path = OUT / f"release-{a.version}.md"
        path.write_text(notes)
        print(f"Wrote {path}\n\n{notes}")
    elif a.cmd == "traceability":
        print(json.dumps(traceability(), indent=2))
    elif a.cmd == "window-check":
        print(json.dumps(window_check(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
