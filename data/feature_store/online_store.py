"""Online feature store (DATA-6): Redis-optional dict-backed online store.

Blueprint Part 8 (Redis online store, l.301), Part 18.1 (online path: per-entity
baseline caching in Redis with TTLs, l.592).

Status: REAL on a pure-python dict store; Redis (7.4.x, port 6379, DATABASE-provisioned)
is OPTIONAL. When ``redis`` is installed and a server is reachable, the SAME read/write
interface serves features from Redis; otherwise an in-process dict with TTL bookkeeping
provides identical semantics so DATA tests and the simulator run with no live Redis.
Swapping in Redis is a config change, not a rewrite (seam 5.10).
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

# ---- optional redis ---------------------------------------------------------
try:  # pragma: no cover - exercised only when redis present + reachable
    import redis  # type: ignore

    _HAVE_REDIS = True
except Exception:  # pragma: no cover
    redis = None  # type: ignore
    _HAVE_REDIS = False


def _online_key(entity: str, key: str) -> str:
    """Redis/online key convention: ``<entity>:<entity_key>`` (see CONTEXT.md feature
    key convention)."""
    return f"{entity}:{key}"


class OnlineStore:
    """Online feature store with a dict fallback and optional Redis backend.

    The same ``write`` / ``read`` interface is used in both modes. TTLs are honoured:
    in dict mode we record an expiry timestamp and treat expired entries as absent.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        *,
        use_redis: bool = False,
    ) -> None:
        self._client: Optional[Any] = None
        self._mem: dict[str, tuple[dict[str, Any], Optional[float]]] = {}
        if use_redis and _HAVE_REDIS:  # pragma: no cover - needs live redis
            try:
                self._client = redis.Redis.from_url(  # type: ignore[union-attr]
                    redis_url or "redis://localhost:6379/0",
                    decode_responses=True,
                )
                self._client.ping()
            except Exception:
                self._client = None  # unreachable -> dict fallback

    @property
    def backend(self) -> str:
        return "redis" if self._client is not None else "memory"

    def write(
        self,
        entity: str,
        key: str,
        values: dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> None:
        k = _online_key(entity, key)
        # JSON-serialize, coercing numpy/pandas scalars to native python.
        payload = {kk: _native(vv) for kk, vv in values.items()}
        if self._client is not None:  # pragma: no cover - needs live redis
            self._client.set(k, json.dumps(payload), ex=ttl_seconds)
            return
        expiry = time.time() + ttl_seconds if ttl_seconds else None
        self._mem[k] = (payload, expiry)

    def read(self, entity: str, key: str) -> Optional[dict[str, Any]]:
        k = _online_key(entity, key)
        if self._client is not None:  # pragma: no cover - needs live redis
            raw = self._client.get(k)
            return json.loads(raw) if raw else None
        entry = self._mem.get(k)
        if entry is None:
            return None
        payload, expiry = entry
        if expiry is not None and time.time() > expiry:
            del self._mem[k]
            return None
        return dict(payload)

    def read_feature(self, entity: str, key: str, feature: str) -> Any:
        row = self.read(entity, key)
        return None if row is None else row.get(feature)


def _native(v: Any) -> Any:
    """Coerce numpy/pandas scalars to JSON-serializable python natives."""
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:  # pragma: no cover
            return v
    return v
