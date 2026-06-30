"""Data-layer connectors (DATA-14; Part 5.2, 32.1, Part 9.1).

Status: SCAFFOLD. Reads synthetic DB-audit, DLP/egress, and bulk-download/export
mock fixtures into the L0 unified event model.

  * DB-audit rows -> channel=``db``, layer=``database``. ``linkage.app_txn_id`` is
    the application txn (or ``None`` -> the DB-write-without-app-txn signal, DATA-20).
  * DLP/egress rows -> channel=``dlp``, layer=``application``; carry bytes-out, the
    egress destination, and the bulk-download flag (carried as object.entitlement_id
    sentinel-free fields; bulk flag preserved via verb + amount=bytes_out).

A single mixed fixture carries ``source`` in {db_audit, dlp}; ``DbAuditDlpAdapter
(source=...)`` filters so the channel invariant holds. Live feeds need creds -> SCAFFOLD.
"""
from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass
from typing import Any

from data.config import is_off_hours, make_id
from data.connectors.base_adapter import IngestMode, SourceAdapter
from data.schemas import Action, Actor, Context, L0Event, Linkage, ObjectRef

_HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(_HERE, "fixtures.json")

# source -> L0 channel
_SOURCE_CHANNEL = {"db_audit": "db", "dlp": "dlp"}
SOURCES = tuple(_SOURCE_CHANNEL)


def _off_hours(ts: str) -> bool:
    hour = int(ts[11:13])
    d = _dt.datetime.strptime(ts[:10], "%Y-%m-%d")
    return is_off_hours(hour, d.weekday())


@dataclass
class DbAuditDlpAdapter(SourceAdapter):
    """DB-audit or DLP/egress log -> L0. ``source`` selects channel (db | dlp)."""

    source: str = "db_audit"

    def __init__(self, source: str = "db_audit", fixture_path: str | None = None,
                 mode: IngestMode = IngestMode.CDC_STREAM) -> None:
        if source not in _SOURCE_CHANNEL:
            raise ValueError(f"unknown source {source!r}; expected one of {SOURCES}")
        super().__init__(source_name=f"dlp_dbaudit_{source}",
                         channel=_SOURCE_CHANNEL[source], mode=mode,
                         fixture_path=fixture_path or FIXTURE)
        self.source = source

    def read(self):
        for row in self.load_fixture():
            if row.get("source") == self.source:
                yield row

    def to_l0(self, raw: dict[str, Any]) -> L0Event:
        ts = raw["ts"]
        emp = raw["employee_id"]
        event_id = make_id("event", raw["source"], raw["log_ref"], emp, ts)
        actor = Actor(employee_id=emp, role=raw.get("role"), branch=raw.get("branch"),
                      privileged_flag=bool(raw.get("privileged", False)))
        if self.source == "db_audit":
            action = Action(verb=raw["verb"], channel="db")
            obj = ObjectRef(table=raw.get("db_table"), amount=raw.get("rows_affected"))
            layer = "database"
            # app_txn_id present -> app-txn<->DB-write link; absent -> the gap signal.
            link = Linkage(app_txn_id=raw.get("app_txn_id"),
                           db_write_id=raw.get("log_ref"))
        else:  # dlp
            action = Action(verb=raw["verb"], channel="dlp")
            # bytes_out -> amount; egress destination -> beneficiary_id; bulk flag in verb.
            verb = "bulk_export" if raw.get("bulk_download") else raw["verb"]
            action = Action(verb=verb, channel="dlp")
            obj = ObjectRef(table=raw.get("dataset"), amount=raw.get("bytes_out"),
                            beneficiary_id=raw.get("channel_dest"))
            layer = "application"
            link = Linkage()
        ctx = Context(ts=ts, src_ip=raw.get("src_ip"), device=raw.get("device"),
                      session_id=raw.get("session_id"), layer=layer,
                      is_off_hours=_off_hours(ts), host=raw.get("host"))
        return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                       object=obj, context=ctx, linkage=link)
