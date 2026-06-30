"""Stdlib test runner (pytest is unavailable in this env).

Discovers data/tests/test_*.py, imports each, runs every top-level callable named
test_*, and reports pass/fail. Exit code is nonzero on any failure.

Usage:  python -m data.tests.run          (from repo root)
"""
from __future__ import annotations

import importlib.util
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TESTS_DIR = os.path.join(ROOT, "data", "tests")


def _load(path: str):
    name = "httest_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    files = sorted(
        os.path.join(TESTS_DIR, f)
        for f in os.listdir(TESTS_DIR)
        if f.startswith("test_") and f.endswith(".py")
    )
    passed = failed = 0
    failures: list[str] = []
    for path in files:
        try:
            mod = _load(path)
        except Exception:
            failed += 1
            failures.append(f"IMPORT {os.path.basename(path)}\n{traceback.format_exc()}")
            continue
        for attr in sorted(dir(mod)):
            if not attr.startswith("test_"):
                continue
            fn = getattr(mod, attr)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
                print(f"  PASS {os.path.basename(path)}::{attr}")
            except Exception:
                failed += 1
                failures.append(f"{os.path.basename(path)}::{attr}\n{traceback.format_exc()}")
                print(f"  FAIL {os.path.basename(path)}::{attr}")
    print(f"\n=== {passed} passed, {failed} failed ===")
    for f in failures:
        print("\n--- FAILURE ---\n" + f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
