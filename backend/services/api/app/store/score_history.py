"""Score-history store (BACKEND — ClickHouse time-series of scored events).

Every scored event from the online stream is appended here, giving a per-entity risk-score timeline
(the ScoreOverTime panel + entity 360). Two layers, both always safe:
  - an in-memory per-entity ring buffer (fast, always available), and
  - ClickHouse persistence when HAWKEYE_CLICKHOUSE_ENABLED=1 and clickhouse-connect is installed +
    reachable (durable, cross-worker, the store's designed home). Guarded — CH being down never
    breaks record()/history(); we simply fall back to memory.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

from app.config import settings

log = logging.getLogger("hawkeye.score_history")

_MAX_PER_ENTITY = 500
_TABLE = "hawkeye_scores"


class ScoreHistoryStore:
    def __init__(self) -> None:
        self._mem: dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_PER_ENTITY))
        self._ch = None
        if settings.clickhouse_enabled:
            self._ch = self._connect_clickhouse()

    def _connect_clickhouse(self):
        try:
            import clickhouse_connect  # type: ignore
            from urllib.parse import urlparse

            u = urlparse(settings.clickhouse_url)
            client = clickhouse_connect.get_client(
                host=u.hostname or "localhost", port=u.port or 8123
            )
            client.command(
                f"CREATE TABLE IF NOT EXISTS {_TABLE} "
                "(ts DateTime, entity_id String, score UInt8, event_id String, note String) "
                "ENGINE = MergeTree ORDER BY (entity_id, ts)"
            )
            log.info("clickhouse score-history enabled at %s", settings.clickhouse_url)
            return client
        except Exception as exc:  # noqa: BLE001 - CH unavailable → memory-only, never fatal
            log.warning("clickhouse disabled (%s); score-history in-memory only", exc)
            return None

    def record(
        self, entity_id: str, ts: str, score: int, event_id: str = "", note: str = ""
    ) -> None:
        point = {"ts": ts, "score": int(score)}
        if event_id:
            point["event_id"] = event_id
        if note:
            point["note"] = note
        self._mem[entity_id].append(point)
        if self._ch is not None:
            try:
                self._ch.insert(
                    _TABLE,
                    [[_dt(ts), entity_id, int(score), event_id, note]],
                    column_names=["ts", "entity_id", "score", "event_id", "note"],
                )
            except Exception:  # noqa: BLE001 - never let a CH hiccup break scoring
                pass

    def history(self, entity_id: str, limit: int = 60) -> list[dict[str, Any]]:
        # Prefer ClickHouse (durable, cross-worker); fall back to the in-memory ring.
        if self._ch is not None:
            try:
                rows = self._ch.query(
                    f"SELECT ts, score, event_id, note FROM {_TABLE} WHERE entity_id = %(e)s "
                    "ORDER BY ts DESC LIMIT %(n)s",
                    parameters={"e": entity_id, "n": limit},
                ).result_rows
                pts = [
                    {"ts": _iso(r[0]), "score": int(r[1]),
                     **({"event_id": r[2]} if r[2] else {}), **({"note": r[3]} if r[3] else {})}
                    for r in reversed(rows)
                ]
                if pts:
                    return pts
            except Exception:  # noqa: BLE001
                pass
        return list(self._mem.get(entity_id, []))[-limit:]

    @property
    def clickhouse_enabled(self) -> bool:
        return self._ch is not None


def _dt(ts: str):
    from datetime import datetime

    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        from app.schemas.common import utcnow

        return utcnow()


def _iso(dt) -> str:
    try:
        return dt.isoformat()
    except Exception:  # noqa: BLE001
        return str(dt)


SCORE_HISTORY = ScoreHistoryStore()
