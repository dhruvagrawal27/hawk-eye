"""HR/IGA connectors (DATA-14; Part 5.2, 32.1, Part 9.1).

Status: SCAFFOLD. Reads synthetic HR/HRMS joiner-mover-leaver (JML), IGA
entitlement-change, and account-modification mock fixtures into the L0 model.

The HR JML feed is the single highest-value context signal (Part 32.1): leaver
notice-period windows gate the bulk-exfiltration-before-resignation typology, and
mover role-changes drive acting-outside-role. The L0 channel is ``hr`` for HR rows
and ``iga`` for IGA rows; ``self_grant`` + short TTL feed the privilege-self-grant
signal (DATA-21). Live HR/IGA feeds need creds -> SCAFFOLD.
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

# source -> channel
_SOURCE_CHANNEL = {"hr": "hr", "iga": "iga"}
SOURCES = tuple(_SOURCE_CHANNEL)


def _off_hours(ts: str) -> bool:
    hour = int(ts[11:13])
    d = _dt.datetime.strptime(ts[:10], "%Y-%m-%d")
    return is_off_hours(hour, d.weekday())


@dataclass
class HrIgaAdapter(SourceAdapter):
    """HR/HRMS JML or IGA entitlement/account-modification log -> L0.

    ``source`` selects the channel (hr | iga). HR is the highest-value JML signal.
    """

    source: str = "hr"

    def __init__(self, source: str = "hr", fixture_path: str | None = None,
                 mode: IngestMode = IngestMode.PERIODIC_BATCH) -> None:
        if source not in _SOURCE_CHANNEL:
            raise ValueError(f"unknown source {source!r}; expected one of {SOURCES}")
        super().__init__(source_name=f"hr_iga_{source}",
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
        jml = raw.get("jml_event")
        actor = Actor(
            employee_id=emp, role=raw.get("role"), dept=raw.get("dept"),
            branch=raw.get("branch"), manager_id=raw.get("manager_id"),
            tenure_days=raw.get("tenure_days"),
            leaver_flag=(jml == "leaver"),
            notice_period=bool(raw.get("notice_period", False)),
            grievance_count=raw.get("grievance_count"),
            grievance_recency_days=raw.get("grievance_recency_days"),
        )
        action = Action(verb=raw["verb"], channel=_SOURCE_CHANNEL[self.source])
        obj = ObjectRef(account_id=raw.get("account_id"),
                        entitlement_id=raw.get("entitlement_id"))
        ctx = Context(ts=ts, src_ip=raw.get("src_ip"), device=raw.get("device"),
                      session_id=raw.get("session_id"), layer="application",
                      is_off_hours=_off_hours(ts))
        # self-grant: granted_by == employee_id -> maker_id == checker_id sentinel.
        granted_by = raw.get("granted_by")
        self_grant = bool(raw.get("self_grant", False)) or (granted_by == emp)
        link = Linkage(
            maker_id=granted_by,
            checker_id=emp if self_grant else None,
        )
        return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                       object=obj, context=ctx, linkage=link)
