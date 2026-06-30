"""Pytest bootstrap: ensure both import roots are on sys.path.

``backend/`` (top-level packages: rules_engine, fusion, serving, regulatory, reliability,
integrations, compliance) and ``backend/services/api`` (the ``app`` package). This mirrors
``[tool.pytest.ini_options] pythonpath`` in pyproject.toml so ``pytest`` works regardless of how it
is invoked.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT / "services" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)
