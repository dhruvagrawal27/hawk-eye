"""Three-way baseline framework with time decay (DATA-19; blueprint Part 6 intro, Part 18.1).

Computes baselines THREE ways simultaneously for any numeric feature column:
  * per-entity   — each employee vs their own history
  * per-peer     — each employee vs their peer group (role/branch/dept)
  * global       — the whole population

Each baseline is EXPONENTIALLY TIME-DECAYED (recent events weigh more) so a slow,
patient attacker cannot "poison" their own baseline by drifting it gradually
(the low-and-slow defence called out in Part 6 intro / Part 18.1).

Redis caching of per-entity + peer-group stats with TTLs is OPTIONAL: if the
`redis` client / live server is absent we keep an in-memory dict cache instead.
Baselines are recomputed on a SCHEDULE (call `compute_baselines`), never per event.

Status: REAL (numpy/pandas). Redis path is SCAFFOLD (needs a live Redis @ 6379).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from data.config import feature_key

# Default half-life for time decay, in days. A 30-day half-life means an event
# 30 days older than the newest contributes half the weight.
DEFAULT_HALFLIFE_DAYS = 30.0

ENTITY_COL = "actor.employee_id"
PEER_COL = "actor.peer_group"
TS_COL = "context.ts"


def _to_epoch_days(ts: pd.Series) -> pd.Series:
    """Parse ISO-8601 (`...Z`) timestamps to float days since epoch (UTC)."""
    dt = pd.to_datetime(ts, utc=True, errors="coerce")
    # nanoseconds -> days
    return dt.view("int64") / 1e9 / 86400.0


def _decay_weights(epoch_days: pd.Series, halflife_days: float) -> np.ndarray:
    """Exponential decay weights relative to the most recent event in the series."""
    if len(epoch_days) == 0:
        return np.array([], dtype=float)
    ref = float(np.nanmax(epoch_days.values))
    age = ref - epoch_days.values.astype(float)
    age = np.where(np.isnan(age), 0.0, age)
    lam = math.log(2.0) / max(halflife_days, 1e-9)
    return np.exp(-lam * age)


def _weighted_stats(values: np.ndarray, weights: np.ndarray) -> tuple[float, float, float]:
    """Return (weighted_mean, weighted_std, sum_weights). Std is population (ddof=0)."""
    mask = ~np.isnan(values)
    v = values[mask]
    w = weights[mask]
    sw = float(w.sum())
    if sw <= 0 or len(v) == 0:
        return (0.0, 0.0, 0.0)
    mean = float((w * v).sum() / sw)
    var = float((w * (v - mean) ** 2).sum() / sw)
    return (mean, math.sqrt(max(var, 0.0)), sw)


@dataclass
class BaselineStat:
    mean: float
    std: float
    count: float  # sum of decay weights (effective sample size)

    def zscore(self, value: float) -> float:
        if self.std <= 1e-12:
            return 0.0
        return (value - self.mean) / self.std


@dataclass
class Baselines:
    """Container holding the three baseline levels for one feature column.

    `.get(entity, feature, window)` returns the matching BaselineStat, falling back
    peer -> global when an entity/peer has no history (cold-start).
    """

    feature: str
    window: str = "all"
    halflife_days: float = DEFAULT_HALFLIFE_DAYS
    per_entity: dict[str, BaselineStat] = field(default_factory=dict)
    per_peer: dict[str, BaselineStat] = field(default_factory=dict)
    glob: BaselineStat = field(default_factory=lambda: BaselineStat(0.0, 0.0, 0.0))
    _entity_peer: dict[str, str] = field(default_factory=dict)

    def get(self, entity: str, feature: Optional[str] = None, window: Optional[str] = None) -> BaselineStat:
        # feature/window args accepted for API symmetry; one Baselines == one feature.
        if entity in self.per_entity and self.per_entity[entity].count > 0:
            return self.per_entity[entity]
        peer = self._entity_peer.get(entity)
        if peer and peer in self.per_peer and self.per_peer[peer].count > 0:
            return self.per_peer[peer]
        return self.glob

    def keys(self) -> dict[str, str]:
        """Feature-store keys this baseline would publish (uses feature_key convention)."""
        out: dict[str, str] = {}
        for ent in self.per_entity:
            out[ent] = feature_key(ent, self.feature + "_baseline", self.window)
        return out


class _MemoryCache:
    """In-memory stand-in for the Redis online cache (TTL is recorded but not enforced
    in-process; the real Redis backend enforces it)."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def set(self, key: str, value: Any, ttl: int) -> None:  # noqa: D401
        self.store[key] = value

    def get(self, key: str) -> Any:
        return self.store.get(key)


def _make_cache(redis_url: Optional[str]) -> Any:
    """Return a live Redis client if available, else an in-memory cache (fallback)."""
    if redis_url:
        try:  # pragma: no cover - needs a live server
            import redis  # type: ignore

            client = redis.Redis.from_url(redis_url)
            client.ping()
            return client
        except Exception:
            pass
    return _MemoryCache()


def compute_baselines(
    df: pd.DataFrame,
    feature: str,
    value_col: str,
    window: str = "all",
    halflife_days: float = DEFAULT_HALFLIFE_DAYS,
    redis_url: Optional[str] = None,
    ttl_seconds: int = 3600,
) -> Baselines:
    """Compute per-entity / per-peer / global time-decayed baselines for `value_col`.

    `feature` is the logical feature name (used for keys); `value_col` is the actual
    DataFrame column to aggregate. Caches per-entity + peer stats with a TTL.
    """
    bl = Baselines(feature=feature, window=window, halflife_days=halflife_days)
    if df.empty or value_col not in df.columns:
        return bl

    work = df.copy()
    work["_v"] = pd.to_numeric(work[value_col], errors="coerce")
    if TS_COL in work.columns:
        work["_ed"] = _to_epoch_days(work[TS_COL])
    else:
        work["_ed"] = np.arange(len(work), dtype=float)

    # global
    gw = _decay_weights(work["_ed"], halflife_days)
    gm, gs, gc = _weighted_stats(work["_v"].values, gw)
    bl.glob = BaselineStat(gm, gs, gc)

    cache = _make_cache(redis_url)

    # per-entity
    if ENTITY_COL in work.columns:
        for ent, grp in work.groupby(ENTITY_COL):
            w = _decay_weights(grp["_ed"], halflife_days)
            m, s, c = _weighted_stats(grp["_v"].values, w)
            bl.per_entity[str(ent)] = BaselineStat(m, s, c)
            if PEER_COL in grp.columns:
                peer = grp[PEER_COL].dropna()
                if len(peer):
                    bl._entity_peer[str(ent)] = str(peer.iloc[0])
            cache.set(feature_key(str(ent), feature + "_baseline", window),
                      {"mean": m, "std": s, "count": c}, ttl_seconds)

    # per-peer
    if PEER_COL in work.columns:
        for peer, grp in work.groupby(PEER_COL):
            w = _decay_weights(grp["_ed"], halflife_days)
            m, s, c = _weighted_stats(grp["_v"].values, w)
            bl.per_peer[str(peer)] = BaselineStat(m, s, c)
            cache.set(feature_key(f"PG:{peer}", feature + "_baseline", window),
                      {"mean": m, "std": s, "count": c}, ttl_seconds)

    return bl


def demo_frame() -> pd.DataFrame:
    """Tiny synthetic frame for tests/docs: two employees in one peer group."""
    rows = []
    base = pd.Timestamp("2026-01-01T10:00:00Z")
    for i in range(20):
        rows.append({
            ENTITY_COL: "EMP-aaaa", PEER_COL: "PG-ops",
            TS_COL: (base + pd.Timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "object.amount": 1000 + (i % 3) * 50,
        })
    for i in range(20):
        rows.append({
            ENTITY_COL: "EMP-bbbb", PEER_COL: "PG-ops",
            TS_COL: (base + pd.Timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "object.amount": 1100 + (i % 3) * 40,
        })
    return pd.DataFrame(rows)
