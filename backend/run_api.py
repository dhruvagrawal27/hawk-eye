"""Local launcher (BACKEND-1): add both import roots and run the API on :8000.

Equivalent to ``uvicorn app.main:app`` run from ``services/api`` but works from ``backend/`` and
ensures the cross-cutting top-level packages (rules_engine, fusion, serving, …) are importable.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
for p in (str(ROOT), str(ROOT / "services" / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

if __name__ == "__main__":
    import uvicorn

    from app.config import settings  # noqa: E402

    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=False)
