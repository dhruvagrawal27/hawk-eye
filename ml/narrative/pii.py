"""PII tokenisation helper (Part 25.3, 25.5).

The narrative gateway only ever sees PII that was ALREADY tokenised upstream
(BACKEND owns the re-identification vault). This helper reproduces the blueprint's
deterministic HMAC-SHA256 token scheme so ML code can tokenise its own fixtures and
verify tokens — it NEVER re-identifies. The key is read from ``os.environ`` and never
hardcoded (golden rule #2).
"""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

# A non-secret default lets fixtures/tests run; production injects PII_HMAC_KEY.
_DEV_FALLBACK_KEY = b"hawkeye-dev-pii-hmac-key-not-for-production"


def _key() -> bytes:
    val = os.environ.get("PII_HMAC_KEY")
    return val.encode() if val else _DEV_FALLBACK_KEY


def tok(value: object, prefix: str = "") -> str:
    """Deterministic keyed token (Part 25.5): ``hmac_sha256(key, value)[:8]``.

    Optionally prefixed, e.g. ``tok("Asha Rao", "EMP")`` -> ``EMP-7f3a1c90``[:].
    """
    digest = hmac.new(_key(), str(value).encode(), hashlib.sha256).hexdigest()[:8]
    return f"{prefix}-{digest}" if prefix else digest


def is_tokenised(value: str) -> bool:
    """Heuristic: looks like one of our token prefixes (EMP-/ACCT-/BEN-/...)."""
    return isinstance(value, str) and "-" in value and value.split("-", 1)[0].isupper()
