"""Durable backend for the alert store (BACKEND-19 persistence).

Keeps the in-memory store as the fast query cache but persists each alert as a JSON payload so it
survives a restart and is shared across workers. Backend is chosen from ``HAWKEYE_DB_URL``:

  ""                       -> disabled (pure in-memory; the default, tests unchanged)
  sqlite:///path | /path   -> stdlib sqlite3 (no extra deps; verifiable anywhere)
  postgresql://...         -> psycopg (guarded import; installed in the API image for deploy)

The schema is intentionally simple — a few indexed columns for filtering + a JSON ``payload`` that
round-trips the full pydantic Alert. Maps onto (or coexists with) the db/ workstream's alerts table.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from typing import Any, Protocol

log = logging.getLogger("hawkeye.persistence")

_DDL_COLS = "(alert_id TEXT PRIMARY KEY, entity_id TEXT, risk_score INTEGER, severity TEXT, status TEXT, created_ts TEXT, payload TEXT, updated_at TEXT)"


class StoreBackend(Protocol):
    def upsert(self, row: dict[str, Any]) -> None: ...
    def upsert_status(self, alert_id: str, status: str) -> None: ...
    def upsert_assignee(self, alert_id: str, assignee: str, status: str) -> None: ...
    def load_all(self) -> list[dict[str, Any]]: ...


class SqliteBackend:
    """Durable sqlite3 backend (stdlib). Thread-safe via a lock + check_same_thread=False."""

    def __init__(self, path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(f"CREATE TABLE IF NOT EXISTS alerts {_DDL_COLS}")
        self._conn.commit()

    def upsert(self, row: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO alerts (alert_id, entity_id, risk_score, severity, status, created_ts, payload, updated_at)"
                " VALUES (:alert_id, :entity_id, :risk_score, :severity, :status, :created_ts, :payload, :updated_at)"
                " ON CONFLICT(alert_id) DO UPDATE SET entity_id=:entity_id, risk_score=:risk_score,"
                " severity=:severity, status=:status, created_ts=:created_ts, payload=:payload, updated_at=:updated_at",
                row,
            )
            self._conn.commit()

    def upsert_status(self, alert_id: str, status: str) -> None:
        with self._lock:
            cur = self._conn.execute("SELECT payload FROM alerts WHERE alert_id=?", (alert_id,))
            row = cur.fetchone()
            if not row:
                return
            payload = json.loads(row[0])
            payload["status"] = status
            self._conn.execute(
                "UPDATE alerts SET status=?, payload=? WHERE alert_id=?",
                (status, json.dumps(payload), alert_id),
            )
            self._conn.commit()

    def upsert_assignee(self, alert_id: str, assignee: str, status: str) -> None:
        with self._lock:
            cur = self._conn.execute("SELECT payload FROM alerts WHERE alert_id=?", (alert_id,))
            row = cur.fetchone()
            if not row:
                return
            payload = json.loads(row[0])
            payload["assignee"] = assignee
            payload["status"] = status
            self._conn.execute(
                "UPDATE alerts SET status=?, payload=? WHERE alert_id=?",
                (status, json.dumps(payload), alert_id),
            )
            self._conn.commit()

    def load_all(self) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT payload FROM alerts")
            return [json.loads(r[0]) for r in cur.fetchall()]


class PgBackend:
    """psycopg backend (guarded import). Same schema; JSON payload as text for portability."""

    def __init__(self, dsn: str) -> None:
        import psycopg  # type: ignore

        self._psycopg = psycopg
        self._dsn = dsn
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS alerts {_DDL_COLS}")
            conn.commit()

    def _connect(self):
        return self._psycopg.connect(self._dsn, autocommit=False)

    def upsert(self, row: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO alerts (alert_id, entity_id, risk_score, severity, status, created_ts, payload, updated_at)"
                " VALUES (%(alert_id)s, %(entity_id)s, %(risk_score)s, %(severity)s, %(status)s, %(created_ts)s, %(payload)s, %(updated_at)s)"
                " ON CONFLICT (alert_id) DO UPDATE SET entity_id=EXCLUDED.entity_id, risk_score=EXCLUDED.risk_score,"
                " severity=EXCLUDED.severity, status=EXCLUDED.status, created_ts=EXCLUDED.created_ts,"
                " payload=EXCLUDED.payload, updated_at=EXCLUDED.updated_at",
                row,
            )
            conn.commit()

    def upsert_status(self, alert_id: str, status: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute("SELECT payload FROM alerts WHERE alert_id=%s", (alert_id,))
            row = cur.fetchone()
            if not row:
                return
            payload = json.loads(row[0])
            payload["status"] = status
            conn.execute(
                "UPDATE alerts SET status=%s, payload=%s WHERE alert_id=%s",
                (status, json.dumps(payload), alert_id),
            )
            conn.commit()

    def upsert_assignee(self, alert_id: str, assignee: str, status: str) -> None:
        with self._lock, self._connect() as conn:
            cur = conn.execute("SELECT payload FROM alerts WHERE alert_id=%s", (alert_id,))
            row = cur.fetchone()
            if not row:
                return
            payload = json.loads(row[0])
            payload["assignee"] = assignee
            payload["status"] = status
            conn.execute(
                "UPDATE alerts SET status=%s, payload=%s WHERE alert_id=%s",
                (status, json.dumps(payload), alert_id),
            )
            conn.commit()

    def load_all(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            cur = conn.execute("SELECT payload FROM alerts")
            return [json.loads(r[0]) for r in cur.fetchall()]


def make_backend(db_url: str) -> StoreBackend | None:
    """Resolve a backend from the URL, or None to disable persistence (in-memory only)."""
    if not db_url:
        return None
    try:
        if db_url.startswith("postgres"):
            return PgBackend(db_url)
        path = db_url[len("sqlite:///") :] if db_url.startswith("sqlite:///") else db_url
        return SqliteBackend(path)
    except Exception as exc:  # noqa: BLE001 - never let a DB hiccup take the API down; degrade to memory
        log.warning("persistence disabled (%s); running in-memory", exc)
        return None
