"""Identity/access connectors (DATA-14; Part 5.2, 32.1, Part 9.1).

Status: SCAFFOLD. Reads synthetic IAM/AD auth, PAM (CyberArk/BeyondTrust)
privileged-session, and VPN mock fixtures into the L0 unified event model.

A single mixed fixture carries ``system`` in {iam, pam, vpn}; the L0 channel is the
system. ``IamPamAdapter(system=...)`` filters to one system so the channel invariant
holds. Live IAM/PAM/VPN feeds (often via the SIEM) need real credentials -> SCAFFOLD.
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

SYSTEMS = ("iam", "pam", "vpn")


def _off_hours(ts: str) -> bool:
    hour = int(ts[11:13])
    d = _dt.datetime.strptime(ts[:10], "%Y-%m-%d")
    return is_off_hours(hour, d.weekday())


@dataclass
class IamPamAdapter(SourceAdapter):
    """IAM/AD auth, PAM privileged-session, or VPN log -> L0. ``system`` is the channel."""

    system: str = "iam"

    def __init__(self, system: str = "iam", fixture_path: str | None = None,
                 mode: IngestMode = IngestMode.CDC_STREAM) -> None:
        if system not in SYSTEMS:
            raise ValueError(f"unknown iam/pam system {system!r}; expected one of {SYSTEMS}")
        super().__init__(source_name=f"iam_pam_{system}", channel=system, mode=mode,
                         fixture_path=fixture_path or FIXTURE)
        self.system = system

    def read(self):
        for row in self.load_fixture():
            if row.get("system") == self.system:
                yield row

    def to_l0(self, raw: dict[str, Any]) -> L0Event:
        ts = raw["ts"]
        emp = raw["employee_id"]
        event_id = make_id("event", raw["system"], raw["log_ref"], emp, ts)
        actor = Actor(employee_id=emp, role=raw.get("role"), branch=raw.get("branch"),
                      privileged_flag=bool(raw.get("privileged", False)))
        action = Action(verb=raw["verb"], channel=self.system)
        # PAM target host -> object.table reused as the privileged target resource ref.
        obj = ObjectRef(table=raw.get("target_host"))
        ctx = Context(ts=ts, src_ip=raw.get("src_ip"), device=raw.get("device"),
                      geo=raw.get("geo"), session_id=raw.get("session_id"),
                      layer="application", is_off_hours=_off_hours(ts),
                      host=raw.get("target_host"))
        link = Linkage()
        return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                       object=obj, context=ctx, linkage=link)
