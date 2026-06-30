"""CBS posting-log adapter (DATA-13; Part 5.2, 32.1, Part 9.1).

Status: SCAFFOLD. Reads a synthetic Finacle/Flexcube/BaNCS/T24-shaped posting-log
mock fixture into the L0 unified event model. Live CBS feeds (CDC / batch extract /
message queue) need real credentials, hence SCAFFOLD.

Channel: ``cbs``. Posting logs carry the maker/checker pairing, customer account,
beneficiary, and amount (integer minor units). ``layer`` = ``application``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from data.config import is_off_hours, make_id
from data.connectors.base_adapter import IngestMode, SourceAdapter
from data.schemas import Action, Actor, Context, L0Event, Linkage, ObjectRef

_HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(_HERE, "fixtures.json")


def _off_hours(ts: str) -> bool:
    # ts like "2026-06-30T02:14:07Z"
    hour = int(ts[11:13])
    # cheap weekday: not derivable without a date lib pulled in; use date parts.
    import datetime as _dt

    d = _dt.datetime.strptime(ts[:10], "%Y-%m-%d")
    return is_off_hours(hour, d.weekday())


@dataclass
class CbsPostingAdapter(SourceAdapter):
    """Finacle/Flexcube/BaNCS/T24 posting-log -> L0 (channel=cbs)."""

    def __init__(self, fixture_path: str | None = None,
                 mode: IngestMode = IngestMode.CDC_STREAM) -> None:
        super().__init__(
            source_name="cbs",
            channel="cbs",
            mode=mode,
            fixture_path=fixture_path or FIXTURE,
        )

    def to_l0(self, raw: dict[str, Any]) -> L0Event:
        ts = raw["ts"]
        emp = raw["teller_id"]
        mc = raw.get("maker_checker")
        event_id = make_id("event", raw["cbs_product"], raw["posting_ref"], emp, ts)
        actor = Actor(
            employee_id=emp,
            role=raw.get("teller_role"),
            branch=raw.get("branch"),
            privileged_flag=bool(raw.get("privileged", False)),
        )
        action = Action(verb=raw["verb"], channel="cbs", maker_checker=mc)
        obj = ObjectRef(
            account_id=raw.get("customer_account"),
            beneficiary_id=raw.get("beneficiary_account"),
            amount=raw.get("amount_minor"),
            currency=raw.get("currency"),
        )
        ctx = Context(
            ts=ts,
            src_ip=raw.get("src_ip"),
            device=raw.get("device"),
            geo=raw.get("geo"),
            session_id=raw.get("session_id"),
            layer="application",
            is_off_hours=_off_hours(ts),
        )
        link = Linkage(
            cbs_ref=raw.get("posting_ref"),
            customer_account=raw.get("customer_account"),
            maker_id=emp if mc == "maker" else None,
            checker_id=emp if mc == "checker" else None,
        )
        return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                       object=obj, context=ctx, linkage=link)
