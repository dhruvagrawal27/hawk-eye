"""Canonical ML test runner — runs each test file in its OWN process (ML-28 / DoD).

Why per-file subprocesses: on macOS, torch and LightGBM each ship their own libomp and
co-loading them into one long-lived process segfaults mid-run (a known platform hazard, not
a test failure). Running each ``tests/ml/test_*.py`` in a fresh subprocess keeps torch-only
and LightGBM-only files isolated, so the whole suite runs green and reproducibly.

Usage:  .mlvenv/bin/python -m ml.tests.run            (from repo root)
        .mlvenv/bin/python -m ml.tests.run test_l3    (substring filter)
Exit code is nonzero if any file fails.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TESTS_DIR = os.path.join(REPO_ROOT, "tests", "ml")
_SUMMARY_RE = re.compile(r"(\d+) (passed|failed|error)")


def _discover(filt: str = "") -> list[str]:
    files = [
        f for f in sorted(os.listdir(TESTS_DIR))
        if f.startswith("test_") and f.endswith(".py") and (filt in f if filt else True)
    ]
    return files


def main(argv: list[str]) -> int:
    filt = argv[0] if argv else ""
    files = _discover(filt)
    if not files:
        print(f"no test files match {filt!r} in {TESTS_DIR}")
        return 1
    env = dict(os.environ)
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    total_pass = total_fail = 0
    failed_files: list[str] = []
    for f in files:
        path = os.path.join(TESTS_DIR, f)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", path, "-q", "-p", "no:cacheprovider"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        )
        out = proc.stdout + proc.stderr
        counts = {kind: int(n) for n, kind in _SUMMARY_RE.findall(out)}
        p, fl = counts.get("passed", 0), counts.get("failed", 0) + counts.get("error", 0)
        total_pass += p
        total_fail += fl
        if proc.returncode == 0:
            print(f"  OK    {f:<28} {p} passed")
        else:
            crash = " (process crashed)" if proc.returncode and proc.returncode > 128 else ""
            print(f"  FAIL  {f:<28} rc={proc.returncode} {p} passed / {fl} failed{crash}")
            failed_files.append(f)
            tail = "\n".join(out.splitlines()[-15:])
            print("    " + tail.replace("\n", "\n    "))
    print("-" * 60)
    status = "GREEN" if not failed_files else "RED"
    print(f"[{status}] {total_pass} passed, {total_fail} failed across {len(files)} files"
          + (f" | failed: {', '.join(failed_files)}" if failed_files else ""))
    return 0 if not failed_files else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
