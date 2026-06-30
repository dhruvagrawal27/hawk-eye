"""Connector tests (DATA-13/14/15/18). Plain test_* functions, bare assert.

Runnable by data/tests/run.py. Each adapter reads its mock fixtures, and every
produced event must pass validate_event and carry the right action.channel.
"""
from __future__ import annotations

from data.connectors import IngestMode, ReadOnlyCollector
from data.connectors.cbs import CbsPostingAdapter
from data.connectors.dlp_dbaudit import DbAuditDlpAdapter
from data.connectors.hr_iga import HrIgaAdapter
from data.connectors.iam_pam import IamPamAdapter
from data.connectors.payments import (
    GlSuspenseNostroAdapter,
    PaymentsMessageAdapter,
    TreasuryBlotterAdapter,
)
from data.connectors.real_telemetry import (
    REAL_SOURCES,
    LabelHook,
    RealTelemetryAdapter,
    pu_positive_unlabelled_split,
    semi_supervised_pool,
)
from data.schemas import validate_event


def _assert_valid(events, channel):
    events = list(events)
    assert events, f"adapter for channel {channel} produced no events"
    for ev in events:
        d = ev.to_dict()
        errs = validate_event(d)
        assert not errs, f"invalid L0 event on channel {channel}: {errs}"
        assert ev.event_id.startswith("evt_"), ev.event_id
        assert ev.action.channel == channel, (
            f"expected channel {channel}, got {ev.action.channel}"
        )
    return events


def test_cbs_adapter():
    evs = _assert_valid(CbsPostingAdapter().stream(), "cbs")
    # posting log carries maker/checker pairing
    assert any(e.action.maker_checker == "maker" for e in evs)
    assert any(e.linkage.cbs_ref for e in evs)


def test_payments_message_rails():
    for rail in ("swift", "rtgs", "neft", "imps", "upi"):
        evs = _assert_valid(PaymentsMessageAdapter(rail=rail).stream(), rail)
        assert all(e.linkage.swift_ref for e in evs)
    # SWIFT row with no CBS posting feeds the recon (DATA-16): cbs_ref is None.
    swift = list(PaymentsMessageAdapter(rail="swift").stream())
    assert any(e.linkage.cbs_ref is None for e in swift)


def test_payments_gl_and_treasury():
    gl = _assert_valid(GlSuspenseNostroAdapter().stream(), "gl")
    # same-person post-and-reconcile signal present in at least one row
    assert any(e.linkage.maker_id == e.linkage.checker_id and e.linkage.maker_id
               for e in gl)
    trd = _assert_valid(TreasuryBlotterAdapter().stream(), "treasury")
    # mismarking signal: observed mark carried alongside reported mark
    assert any(e.linkage.db_write_id is not None for e in trd)


def test_iam_pam_vpn():
    _assert_valid(IamPamAdapter(system="iam").stream(), "iam")
    pam = _assert_valid(IamPamAdapter(system="pam").stream(), "pam")
    assert all(e.actor.privileged_flag for e in pam)
    _assert_valid(IamPamAdapter(system="vpn").stream(), "vpn")


def test_db_audit_and_dlp():
    db = _assert_valid(DbAuditDlpAdapter(source="db_audit").stream(), "db")
    assert all(e.context.layer == "database" for e in db)
    # DB write with no app txn -> the gap signal
    assert any(e.linkage.app_txn_id is None for e in db)
    dlp = _assert_valid(DbAuditDlpAdapter(source="dlp").stream(), "dlp")
    # bulk export flagged in the verb
    assert any(e.action.verb == "bulk_export" for e in dlp)


def test_hr_iga():
    hr = _assert_valid(HrIgaAdapter(source="hr").stream(), "hr")
    # leaver JML sets leaver_flag + notice_period (highest-value signal)
    assert any(e.actor.leaver_flag and e.actor.notice_period for e in hr)
    iga = _assert_valid(HrIgaAdapter(source="iga").stream(), "iga")
    # self-grant -> maker_id == employee, checker_id == employee
    assert any(e.linkage.maker_id == e.actor.employee_id
               and e.linkage.checker_id == e.actor.employee_id for e in iga)


def test_read_only_collector():
    col = ReadOnlyCollector(adapter=CbsPostingAdapter())
    assert col.enforce is False
    assert col.mode == IngestMode.CDC_STREAM
    evs = list(col.poll())
    assert evs and all(not validate_event(e.to_dict()) for e in evs)


def test_collector_rejects_enforce():
    raised = False
    try:
        ReadOnlyCollector(adapter=CbsPostingAdapter(), enforce=True)
    except ValueError:
        raised = True
    assert raised, "collector must reject enforce=True (ALERT-ONLY)"


def test_real_telemetry_scaffold_all_sources():
    for src in REAL_SOURCES:
        adp = RealTelemetryAdapter(source=src)
        evs = list(adp.stream())
        assert evs, f"real_telemetry source {src} produced no events"
        for ev in evs:
            assert not validate_event(ev.to_dict())
            assert ev.action.channel == adp.channel
        # label hooks default to unlabelled (no live source wired)
        assert adp.label_for(evs[0].event_id, LabelHook.GOLD) is None


def test_real_telemetry_live_reader_seam():
    # supplying a live_reader swaps the source; to_l0 mapping is unchanged.
    rows = [{
        "cbs_product": "finacle", "posting_ref": "LIVE-1", "ts": "2026-06-30T03:00:00Z",
        "teller_id": "EMP-aaaa", "teller_role": "ops_maker", "branch": "BR-001",
        "verb": "create_beneficiary", "maker_checker": "maker",
        "customer_account": "ACCT-1", "beneficiary_account": "BEN-1",
        "amount_minor": None, "currency": "INR",
    }]
    adp = RealTelemetryAdapter(source="cbs", live_reader=lambda: rows)
    evs = list(adp.stream())
    assert len(evs) == 1
    assert evs[0].action.channel == "cbs"
    assert not validate_event(evs[0].to_dict())


def test_pu_and_semi_supervised_entrypoints():
    evs = list(RealTelemetryAdapter(source="cbs").stream())
    # mark the first event positive, rest unlabelled
    pos_id = evs[0].event_id
    positives, unlabelled = pu_positive_unlabelled_split(
        evs, lambda e: True if e.event_id == pos_id else None
    )
    assert len(positives) == 1
    assert len(unlabelled) == len(evs) - 1
    labelled, unlab = semi_supervised_pool(
        evs, lambda e: True if e.event_id == pos_id else None
    )
    assert len(labelled) == 1 and labelled[0][1] is True
    assert len(unlab) == len(evs) - 1
