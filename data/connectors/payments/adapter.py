"""Payments connectors (DATA-13; Part 5.2, 32.1, Part 9.1).

Status: SCAFFOLD. Reads synthetic mock fixtures into the L0 unified event model:

  * ``PaymentsMessageAdapter`` — SWIFT/RTGS/NEFT/IMPS/UPI message logs. The L0
    ``action.channel`` is the rail (``swift``/``rtgs``/``neft``/``imps``/``upi``);
    ``linkage.swift_ref`` holds the instrument message ref and ``linkage.cbs_ref``
    the matching CBS posting (or ``None`` -> feeds the SWIFT↔CBS recon, DATA-16).
  * ``GlSuspenseNostroAdapter`` — GL / suspense / nostro ledger entries
    (channel=``gl``); carries aging + same-person post-and-reconcile signal fields.
  * ``TreasuryBlotterAdapter`` — trade/treasury blotter (channel=``treasury``);
    carries reported-vs-observed mark for the mismarking / rogue-trader signal.

Live feeds need real credentials, hence SCAFFOLD.
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
FIXTURE_MESSAGES = os.path.join(_HERE, "fixtures.json")
FIXTURE_GL = os.path.join(_HERE, "gl_suspense_nostro.json")
FIXTURE_TREASURY = os.path.join(_HERE, "treasury_blotter.json")

# A message-log fixture mixes rails; we expose one adapter per rail by filtering.
RAILS = ("swift", "rtgs", "neft", "imps", "upi")


def _off_hours(ts: str) -> bool:
    hour = int(ts[11:13])
    d = _dt.datetime.strptime(ts[:10], "%Y-%m-%d")
    return is_off_hours(hour, d.weekday())


@dataclass
class PaymentsMessageAdapter(SourceAdapter):
    """SWIFT/RTGS/NEFT/IMPS/UPI message-log -> L0.

    ``rail`` selects which rows the adapter emits and is the L0 channel. The message
    fixture mixes rails; ``read()`` filters to the configured rail so the adapter's
    ``channel`` invariant (action.channel == rail) holds for every produced event.
    """

    rail: str = "swift"

    def __init__(self, rail: str = "swift", fixture_path: str | None = None,
                 mode: IngestMode = IngestMode.CDC_STREAM) -> None:
        if rail not in RAILS:
            raise ValueError(f"unknown payments rail {rail!r}; expected one of {RAILS}")
        super().__init__(
            source_name=f"payments_{rail}",
            channel=rail,
            mode=mode,
            fixture_path=fixture_path or FIXTURE_MESSAGES,
        )
        self.rail = rail

    def read(self):
        for row in self.load_fixture():
            if row.get("rail") == self.rail:
                yield row

    def to_l0(self, raw: dict[str, Any]) -> L0Event:
        ts = raw["ts"]
        emp = raw["operator_id"]
        mc = raw.get("maker_checker")
        event_id = make_id("event", raw["rail"], raw["msg_ref"], emp, ts)
        actor = Actor(employee_id=emp, role=raw.get("operator_role"),
                      branch=raw.get("branch"))
        action = Action(verb=raw["verb"], channel=self.rail, maker_checker=mc)
        obj = ObjectRef(
            account_id=raw.get("ordering_account"),
            beneficiary_id=raw.get("beneficiary_account"),
            instrument=raw.get("instrument"),
            amount=raw.get("amount_minor"),
            currency=raw.get("currency"),
        )
        ctx = Context(ts=ts, src_ip=raw.get("src_ip"), device=raw.get("device"),
                      session_id=raw.get("session_id"), layer="application",
                      is_off_hours=_off_hours(ts))
        link = Linkage(
            swift_ref=raw.get("msg_ref"),
            cbs_ref=raw.get("cbs_posting_ref"),
            customer_account=raw.get("ordering_account"),
            maker_id=emp if mc == "maker" else None,
            checker_id=emp if mc == "checker" else None,
        )
        return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                       object=obj, context=ctx, linkage=link)


@dataclass
class GlSuspenseNostroAdapter(SourceAdapter):
    """GL / suspense / nostro ledger entries -> L0 (channel=gl)."""

    def __init__(self, fixture_path: str | None = None,
                 mode: IngestMode = IngestMode.PERIODIC_BATCH) -> None:
        super().__init__(source_name="gl_suspense_nostro", channel="gl", mode=mode,
                         fixture_path=fixture_path or FIXTURE_GL)

    def to_l0(self, raw: dict[str, Any]) -> L0Event:
        ts = raw["ts"]
        emp = raw["operator_id"]
        mc = raw.get("maker_checker")
        event_id = make_id("event", raw["ledger"], raw["entry_ref"], emp, ts)
        actor = Actor(employee_id=emp, role=raw.get("operator_role"),
                      branch=raw.get("branch"),
                      privileged_flag=bool(raw.get("privileged", False)))
        action = Action(verb=raw["verb"], channel="gl", maker_checker=mc)
        obj = ObjectRef(account_id=raw.get("gl_account"),
                        amount=raw.get("amount_minor"), currency=raw.get("currency"))
        ctx = Context(ts=ts, src_ip=raw.get("src_ip"), device=raw.get("device"),
                      session_id=raw.get("session_id"), layer="application",
                      is_off_hours=_off_hours(ts))
        # same-person post-and-reconcile signal: maker == reconciled_by
        link = Linkage(
            cbs_ref=raw.get("entry_ref"),
            customer_account=raw.get("gl_account"),
            maker_id=emp if mc == "maker" else None,
            checker_id=raw.get("reconciled_by"),
        )
        return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                       object=obj, context=ctx, linkage=link)


@dataclass
class TreasuryBlotterAdapter(SourceAdapter):
    """Trade / treasury blotter -> L0 (channel=treasury).

    Reported vs observed mark go into object.amount (reported) and the linkage
    db_write_id field is reused to carry the observed mark as a string so the
    mismarking / P&L-vs-mark divergence feature (DATA-20) can compute drift.
    """

    def __init__(self, fixture_path: str | None = None,
                 mode: IngestMode = IngestMode.PERIODIC_BATCH) -> None:
        super().__init__(source_name="treasury_blotter", channel="treasury", mode=mode,
                         fixture_path=fixture_path or FIXTURE_TREASURY)

    def to_l0(self, raw: dict[str, Any]) -> L0Event:
        ts = raw["ts"]
        emp = raw["trader_id"]
        event_id = make_id("event", raw["desk"], raw["trade_ref"], emp, ts)
        actor = Actor(employee_id=emp, role=raw.get("trader_role"),
                      branch=raw.get("branch"))
        action = Action(verb=raw["verb"], channel="treasury")
        obj = ObjectRef(instrument=raw.get("instrument"),
                        amount=raw.get("reported_mark_minor"),
                        currency=raw.get("currency"))
        ctx = Context(ts=ts, src_ip=raw.get("src_ip"), device=raw.get("device"),
                      session_id=raw.get("session_id"), layer="application",
                      is_off_hours=_off_hours(ts))
        observed = raw.get("observed_mark_minor")
        link = Linkage(
            swift_ref=raw.get("trade_ref"),
            db_write_id=str(observed) if observed is not None else None,
        )
        return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                       object=obj, context=ctx, linkage=link)
