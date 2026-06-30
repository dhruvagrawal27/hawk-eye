"""ML-serving health probe for the degradation switch (PLATFORM-4).

Polls the serving v2 readiness endpoint. If serving is unhealthy (or a forced override
is set), the switch routes scoring to L1-rules-only. Cached briefly to avoid hammering.
"""
from __future__ import annotations

import os
import time

import httpx

SERVING_HEALTH_URL = os.environ.get("ML_SERVING_HEALTH_URL", "http://serving:8001/v2/health/ready")
FORCE_RULES_ONLY = os.environ.get("DEGRADATION_FORCE_RULES_ONLY", "false").lower() == "true"
_CACHE_TTL = 5.0

_state = {"healthy": False, "checked": 0.0, "forced": FORCE_RULES_ONLY}


def set_forced(value: bool) -> None:
    _state["forced"] = value


def is_forced() -> bool:
    return bool(_state["forced"])


def serving_healthy(force_check: bool = False) -> bool:
    now = time.monotonic()
    if not force_check and (now - _state["checked"]) < _CACHE_TTL:
        return bool(_state["healthy"])
    try:
        r = httpx.get(SERVING_HEALTH_URL, timeout=2.0)
        _state["healthy"] = r.status_code == 200
    except Exception:
        _state["healthy"] = False
    _state["checked"] = now
    return bool(_state["healthy"])


def current_mode() -> str:
    """Decide routing mode. Forced override OR unhealthy serving => rules_only."""
    if _state["forced"]:
        return "rules_only"
    return "full" if serving_healthy() else "rules_only"
