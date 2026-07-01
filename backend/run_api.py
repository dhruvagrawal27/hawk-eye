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

# Load the repo-root .env (NEAR_AI_API_KEY / GROQ_API_KEY / HAWKEYE_* / PII_HMAC_KEY) into the
# environment BEFORE app.config is imported, so a local `python run_api.py` picks up the same secrets
# the Docker deploy gets via compose `env_file`, regardless of the directory it's launched from.
# (In Docker these already arrive as real env vars, which take precedence — this is the local seam.)
try:  # pragma: no cover - convenience for local runs; absent dotenv just means rely on the shell env
    from dotenv import load_dotenv

    load_dotenv(ROOT.parent / ".env")
except Exception:  # noqa: BLE001
    pass

if __name__ == "__main__":
    import uvicorn

    from app.config import settings  # noqa: E402

    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=False)
