"""RED-TEAM: RBAC + Separation-of-Duties + immutable audit + contestability.

Adversarial probes of the Hawk-Eye backend control-plane invariants
(FROZEN bank-org-chart RBAC 12x9 — docs/BANK_ROLES.md, Part 19.6 SoD, Part 16 natural
justice, Part 29.2 contestability; BACKEND.md sections 3/4).

Every test ASSERTS that a blueprint invariant HOLDS. A FAILING assert is a real
violation. We exercise the real FastAPI handlers via TestClient where possible, and
probe the auth/SoD primitives directly where a route cannot be reached.

Run:
    .bevenv/bin/python -m pytest tests/redteam/test_rbac_sod_audit.py -q -p no:cacheprovider
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# --- import-root bootstrap (this file lives at repo-root tests/redteam, NOT under
# backend/, so backend/conftest.py does not run for us). Mirror backend/conftest.py.
_BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
for _p in (str(_BACKEND), str(_BACKEND / "services" / "api")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.audit.writer import AUDIT  # noqa: E402
from app.auth import sod  # noqa: E402
from app.auth.principal import Principal  # noqa: E402
from app.auth.rbac import MATRIX, is_allowed  # noqa: E402
from app.schemas.alerts import Alert  # noqa: E402
from app.schemas.audit import AuditEvent  # noqa: E402
from app.schemas.common import Capability, Role  # noqa: E402
from app.store.alert_store import ALERTS  # noqa: E402

DEV_PASSWORD = "hawk-eye"

# Seeded synthetic users (mirrors backend/tests/conftest.py ROLE_USER). The friendly keys are
# legacy test labels resolving to the FROZEN bank-org-chart personas / login aliases
# (docs/BANK_ROLES.md old→new): analyst→relationship_manager, senior→branch_manager,
# lead→agm_vigilance, compliance→dgm_compliance, auditor→chief_internal_auditor,
# model_engineer→data_science_lead, admin→it_admin.
ROLE_USER = {
    "analyst": "EMP-an01",
    "senior": "EMP-sr01",
    "lead": "EMP-tl01",
    "compliance": "EMP-co01",
    "compliance2": "EMP-co02",
    "auditor": "EMP-au01",
    "model_engineer": "EMP-me01",
    "admin": "EMP-pa01",
    "service": "svc-ingest",
}


# --------------------------------------------------------------------------------------
# Fixtures — reset in-memory stores and reseed before each test (this file does not get
# the backend/tests/conftest.py autouse reset, so we do it ourselves).
# --------------------------------------------------------------------------------------
def _reset_state() -> None:
    from app.store.entity_store import ENTITIES
    from app.store.rule_change_store import RULE_CHANGES
    from app.store.seed import seed_demo
    from app.store.user_store import USER_STORE

    ALERTS._alerts.clear()
    ALERTS._dispositions.clear()
    ALERTS._block_requests.clear()
    ALERTS._narrative_memos.clear()
    ALERTS._feedback_queue.clear()
    ENTITIES._profiles.clear()
    ENTITIES._timelines.clear()
    ENTITIES._graphs.clear()
    ENTITIES._peers.clear()
    RULE_CHANGES._proposals.clear()
    AUDIT._events.clear()
    for u in USER_STORE.list():
        if u.role == Role.RELATIONSHIP_MANAGER:
            u.assigned_alerts.clear()
            u.assigned_alerts.add("alr_demo01")
    seed_demo()


@pytest.fixture(autouse=True)
def _reset():
    _reset_state()
    yield
    _reset_state()


@pytest.fixture()
def client():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    def _auth(role: str) -> dict:
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": ROLE_USER[role], "password": DEV_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _auth


# ======================================================================================
# 1. RBAC — each protected route enforces its minimum capability/role (BACKEND.md §3).
#    Attack: call protected routes as a lower / wrong role -> must be 401/403.
# ======================================================================================
def test_unauthenticated_requests_are_rejected(client):
    """No bearer token => 401 on every protected route (defence: get_principal)."""
    for path in ("/api/v1/alerts", "/api/v1/audit", "/api/v1/models", "/api/v1/rules"):
        r = client.get(path)
        assert r.status_code == 401, f"{path} reachable without auth: {r.status_code}"


def test_garbage_and_tampered_tokens_rejected(client):
    """A forged / non-JWT bearer token must be rejected (signature validation)."""
    for tok in ("not-a-jwt", "Bearer", "a.b.c", "x" * 64):
        r = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {tok}"})
        assert (
            r.status_code == 401
        ), f"forged token accepted: {tok!r} -> {r.status_code}"


def test_analyst_cannot_reach_higher_capability_routes(client, auth):
    """Relationship Manager has neither tune_rules / train_deploy_models / view_audit / admin."""
    a = auth("analyst")
    forbidden = [
        ("get", "/api/v1/rules"),
        ("get", "/api/v1/models"),
        ("get", "/api/v1/drift"),
        ("get", "/api/v1/audit"),
        ("get", "/api/v1/admin/users"),
    ]
    for method, path in forbidden:
        r = getattr(client, method)(path, headers=a)
        assert r.status_code == 403, f"analyst reached {path}: {r.status_code}"


def test_auditor_is_read_only_cannot_write(client, auth):
    """Chief Internal Auditor may view_audit but NOT disposition / assign / unmask (read-only)."""
    a = auth("auditor")
    r = client.post(
        "/api/v1/alerts/alr_demo01/disposition",
        headers=a,
        json={"outcome": "fraud", "notes": "x", "evidence_ids": []},
    )
    assert r.status_code == 403, f"auditor wrote a disposition: {r.status_code}"
    r = client.post(
        "/api/v1/alerts/alr_demo01/assign", headers=a, json={"assignee": "EMP-an01"}
    )
    assert r.status_code == 403, f"auditor assigned an alert: {r.status_code}"


def test_platform_admin_sees_no_case_data(client, auth):
    """IT Admin = deploy-infra + admin only; VIEW_ALERTS is DENY (docs/BANK_ROLES.md)."""
    a = auth("admin")
    assert client.get("/api/v1/alerts", headers=a).status_code == 403
    assert client.get("/api/v1/alerts/alr_demo01", headers=a).status_code == 403


def test_analyst_cannot_unmask_senior_only_pii_without_justification(client, auth):
    """PII unmask: Relationship Manager is case-scoped+logged and MUST justify; bare unmask => 403."""
    a = auth("analyst")
    r = client.post("/api/v1/entities/EMP-7f3a/unmask", headers=a, json={})
    assert (
        r.status_code == 403
    ), f"analyst unmasked PII with no justification: {r.status_code}"


def test_model_engineer_cannot_unmask_pii_at_all(client, auth):
    """unmask_pii is DENY for Data Science Lead (de-identified-only). Must be 403."""
    a = auth("model_engineer")
    r = client.post(
        "/api/v1/entities/EMP-7f3a/unmask",
        headers=a,
        json={"justification": "I want the real name"},
    )
    assert r.status_code == 403, f"model engineer unmasked PII: {r.status_code}"


def test_service_account_scoped_token_cannot_read_alerts_or_audit(client, auth):
    """Service account = scoped_token / write_only: cannot READ alerts or the audit trail."""
    a = auth("service")
    assert client.get("/api/v1/alerts", headers=a).status_code == 403
    assert client.get("/api/v1/audit", headers=a).status_code == 403


def test_rbac_matrix_is_complete_12x9(client):
    """Defence: the matrix must encode all 12 roles x 9 capabilities (no missing cell)."""
    assert len(MATRIX) == 12
    assert set(MATRIX) == set(Role)
    for role, row in MATRIX.items():
        assert len(row) == 9, f"{role} has {len(row)} caps"
        for cap in Capability:
            assert cap in row, f"{role} missing {cap}"


# ======================================================================================
# 2. Separation of Duties (BACKEND.md §4 / Part 19.6). Attack each SoD rule directly +
#    via routes: deployer cannot label/close; no self-review; four-eyes on rule changes
#    (approve = DGM Compliance only); model promotion needs a distinct second-person signoff.
# ======================================================================================
def _principal(user_id: str, role: Role, **kw) -> Principal:
    return Principal(user_id=user_id, role=role, **kw)


def test_sod_deployer_cannot_label_or_close_alerts():
    """A model deployer (train_deploy_models) may not write labels / close alerts."""
    me = _principal("EMP-me01", Role.DATA_SCIENCE_LEAD, de_identified_only=True)
    with pytest.raises(sod.SoDError):
        sod.check_disposition(me, alert_owner=None, subject_entity="EMP-7f3a")
    # And at RBAC level disposition itself is DENY for the deployer.
    assert not is_allowed(Role.DATA_SCIENCE_LEAD, Capability.DISPOSITION)


def test_sod_no_self_review_via_route(client, auth):
    """No one may disposition an alert ABOUT themselves (self-review). Probe the route."""
    # Craft an alert whose subject entity == the senior investigator's own user id.
    ALERTS.add(
        Alert(
            alert_id="alr_self",
            entity_id="EMP-sr01",
            risk_score=80,
            severity="high",
            confidence=0.8,
            created_ts="2026-06-30T00:00:00Z",
            reason_codes=[{"source": "rule", "code": "X", "detail": "d"}],
        )
    )
    r = client.post(
        "/api/v1/alerts/alr_self/disposition",
        headers=auth("senior"),
        json={
            "outcome": "false_positive",
            "notes": "clearing myself",
            "evidence_ids": [],
        },
    )
    assert r.status_code == 403, f"self-review disposition allowed: {r.status_code}"
    assert "self_review" in r.text or "own case" in r.text


def test_sod_investigator_cannot_tune_own_alert_rules():
    """An investigator may not unilaterally tune a rule that generated THEIR alert."""
    an = _principal(
        "EMP-an01", Role.RELATIONSHIP_MANAGER, assigned_alerts={"alr_demo01"}
    )
    with pytest.raises(sod.SoDError):
        sod.check_rule_tuning(an, generated_alerts={"alr_demo01", "alr_other"})
    # Defence-in-depth at RBAC: branch-line investigators lack tune_rules entirely.
    assert not is_allowed(Role.RELATIONSHIP_MANAGER, Capability.TUNE_RULES)
    assert not is_allowed(Role.BRANCH_MANAGER, Capability.TUNE_RULES)


def test_sod_four_eyes_self_approval_rejected_on_rules(client, auth):
    """Whoever proposes a rule change cannot approve it (four-eyes, proposer != approver)."""
    co = auth("compliance")
    r = client.post(
        "/api/v1/rules",
        headers=co,
        json={
            "code": "OFF_HOURS_ACTIVITY",
            "change_reason": "tighten",
            "params": {"window": 2},
        },
    )
    assert r.status_code == 201, r.text
    change_id = r.json()["change_id"]
    r2 = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=co,  # SAME proposer
        json={"change_id": change_id, "approve": True},
    )
    assert r2.status_code == 403, f"self-approved a rule change: {r2.status_code}"


def test_sod_only_compliance_approves_rule_change_team_lead_propose_only(client, auth):
    """approve = DGM Compliance only; AGM Vigilance is propose-only and rejected on approve."""
    co = auth("compliance")
    change_id = client.post(
        "/api/v1/rules",
        headers=co,
        json={
            "code": "OFF_HOURS_ACTIVITY",
            "change_reason": "x",
            "params": {"window": 3},
        },
    ).json()["change_id"]
    # AGM Vigilance has tune_rules (propose_only) but MUST NOT be able to approve.
    r = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=auth("lead"),
        json={"change_id": change_id, "approve": True},
    )
    assert (
        r.status_code == 403
    ), f"AGM Vigilance approved a rule change: {r.status_code}"
    # A SECOND, distinct DGM Compliance is the proper four-eyes approver.
    r2 = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=auth("compliance2"),
        json={"change_id": change_id, "approve": True},
    )
    assert r2.status_code == 200, r2.text


def test_sod_model_promotion_requires_distinct_signoff(client, auth):
    """Model promotion needs a second-person sign-off (promoter != approver)."""
    me = auth("model_engineer")
    # No sign-off.
    r = client.post(
        "/api/v1/models/l3_lightgbm/promote?version=stub-2026.06.30",
        headers=me,
        json={"to_stage": "Production", "signoff_by": ""},
    )
    assert r.status_code == 403, f"promotion with no sign-off allowed: {r.status_code}"
    # Self sign-off.
    r2 = client.post(
        "/api/v1/models/l3_lightgbm/promote?version=stub-2026.06.30",
        headers=me,
        json={"to_stage": "Production", "signoff_by": "EMP-me01"},
    )
    assert r2.status_code == 403, f"self sign-off promotion allowed: {r2.status_code}"


def test_sod_platform_admin_cannot_promote_models(client, auth):
    """IT Admin is deploy-infra-only; promoting a model artifact is Data-Science-Lead-only."""
    r = client.post(
        "/api/v1/models/l3_lightgbm/promote?version=stub-2026.06.30",
        headers=auth("admin"),
        json={"to_stage": "Production", "signoff_by": "EMP-me01"},
    )
    assert r.status_code == 403, f"IT admin promoted a model: {r.status_code}"


def test_sod_pii_unmask_is_a_separate_capability_not_implied_by_view():
    """unmask_pii must be an independent capability — never implied by view_alerts."""
    for role in Role:
        if is_allowed(role, Capability.UNMASK_PII):
            # If a role can unmask, that is an explicit grant, but the converse must hold:
            # viewing alerts must NEVER on its own confer unmask.
            pass
    # The Chief Internal Auditor can read alerts (read_only) yet must NOT be able to unmask.
    assert is_allowed(Role.CHIEF_INTERNAL_AUDITOR, Capability.VIEW_ALERTS)
    assert not is_allowed(
        Role.CHIEF_INTERNAL_AUDITOR, Capability.UNMASK_PII
    ), "view-only Chief Internal Auditor was granted PII unmask — separation broken"


# ======================================================================================
# 3. Audit trail — every sensitive action writes an immutable audit entry incl.
#    who-viewed-whom; tampering / deletion must be prevented or detected (Part 19.3/29.2).
# ======================================================================================
def test_sensitive_actions_write_who_viewed_whom_audit(client, auth):
    """disposition / unmask / block-request / rule-change all leave an audit trail."""
    before = len(AUDIT.all())
    # who-viewed-whom on a single-alert view
    client.get("/api/v1/alerts/alr_demo01", headers=auth("senior"))
    view_events = [e for e in AUDIT.all() if e.action == "alert.view"]
    assert view_events, "single-alert view did not write a who-viewed-whom audit event"
    assert any(
        e.target == "EMP-7f3a" for e in view_events
    ), "viewed entity not recorded"
    # PII unmask is audited
    client.post(
        "/api/v1/entities/EMP-7f3a/unmask",
        headers=auth("senior"),
        json={"justification": "case work"},
    )
    assert any(e.action == "pii.unmask" for e in AUDIT.all()), "unmask not audited"
    assert len(AUDIT.all()) > before


def test_audit_entries_are_tamper_evident_or_immutable():
    """A written audit entry must not be silently mutable in place (Part 19.3 WORM).

    ATTACK: write an audit entry, then try to rewrite who-did-what on the stored object
    obtained from the writer's public accessors. An append-only WORM trail must either
    reject the mutation (frozen model / defensive copy) OR carry tamper-evidence
    (hash / chain / signature) so the change is DETECTABLE. If neither holds, an insider
    who reaches the trail can erase 'who-viewed-whom' — defeating natural justice.
    """
    ev = AUDIT.write(
        actor="EMP-snoop",
        actor_role=Role.BRANCH_MANAGER,
        action="pii.unmask",
        target="EMP-victim",
        detail={"tokens": ["EMP-victim"]},
    )
    original_actor = ev.actor
    stored = [e for e in AUDIT.all() if e.audit_id == ev.audit_id][0]

    tamper_blocked = False
    try:
        stored.actor = "EMP-someone-else"
        stored.action = "noop"
        stored.target = None
    except (TypeError, ValueError, AttributeError):
        tamper_blocked = True

    # Re-read from the writer to see whether the trail now reflects the forgery.
    after = [e for e in AUDIT.all() if e.audit_id == ev.audit_id][0]
    tamper_visible_in_store = after.actor != original_actor

    has_integrity_field = any(
        f in AuditEvent.model_fields
        for f in ("hash", "prev_hash", "signature", "digest")
    )

    assert tamper_blocked or not tamper_visible_in_store or has_integrity_field, (
        "Audit entries are mutable in place AND the writer hands out live references "
        "with no hash-chain/signature: an insider can rewrite who-viewed-whom on the "
        f"stored trail undetectably (actor {original_actor!r} -> {after.actor!r}). "
        "The immutable=True flag is decorative."
    )


def test_audit_query_and_all_do_not_let_caller_delete_history():
    """Reading the trail must not expose a handle that deletes/clears prior history."""
    AUDIT.write(
        actor="EMP-a",
        actor_role=Role.RELATIONSHIP_MANAGER,
        action="alert.view",
        target="E1",
    )
    n = len(AUDIT.all())
    # The public list returned by all()/query() must be a copy: clearing it must NOT
    # wipe the underlying trail.
    snapshot = AUDIT.all()
    snapshot.clear()
    items, _ = AUDIT.query()
    page = items
    page.clear()
    assert len(AUDIT.all()) >= n, "audit history was deleted via a returned list handle"


def test_reading_audit_is_itself_audited(client, auth):
    """watch-the-watchers: reading the audit trail writes an audit.view event."""
    auditor = auth("auditor")
    client.get("/api/v1/audit", headers=auditor)
    assert any(
        e.action == "audit.view" for e in AUDIT.all()
    ), "reading the audit trail was not itself audited"


def test_view_own_audit_scope_enforced_for_senior(client, auth):
    """Branch Manager gets view_own audit only — cannot read others' entries."""
    # Seed an audit entry by a different actor.
    AUDIT.write(
        actor="EMP-other",
        actor_role=Role.RELATIONSHIP_MANAGER,
        action="alert.view",
        target="E9",
    )
    r = client.get("/api/v1/audit", headers=auth("senior"))
    assert r.status_code == 200, r.text
    for item in r.json()["items"]:
        assert (
            item["actor"] == "EMP-sr01"
        ), f"senior saw another actor's audit entry: {item['actor']} (view_own breached)"


# ======================================================================================
# 4. Contestability (Part 29.2 / Part 16 natural justice). Every alert must carry
#    reason_codes (+ a narrative path) so it is contestable. An alert WITHOUT reason
#    codes must be rejected or flagged — never silently served as actionable.
# ======================================================================================
def test_every_seeded_alert_carries_reason_codes(client, auth):
    """All real/seeded alerts surfaced to a human must have at least one reason code."""
    r = client.get("/api/v1/alerts", headers=auth("senior"))
    assert r.status_code == 200, r.text
    for alert in r.json()["items"]:
        assert alert[
            "reason_codes"
        ], f"alert {alert['alert_id']} served with NO reason codes — not contestable"


def test_alert_without_reason_codes_is_rejected_or_flagged(client, auth):
    """ATTACK: inject a reason-code-less alert and confirm it cannot be served as a
    normal, actionable alert.

    Part 29.2 (contestability) + Part 16 (natural justice) require every alert to carry
    reason codes and a narrative path so the accused can contest it. If the schema/store
    accept an empty ``reason_codes`` list AND the API serves that alert with status 200
    and an empty reason set, the system can produce an un-contestable accusation — a
    direct violation. A correct implementation either (a) refuses to construct such an
    alert, (b) refuses to store it, or (c) refuses to serve it (404/422) — at minimum it
    must not return it as a normal 200 with empty reason codes.
    """
    rejected_at_construction = False
    try:
        bad = Alert(
            alert_id="alr_noreason",
            entity_id="EMP-2b14",
            risk_score=70,
            severity="high",
            confidence=0.7,
            created_ts="2026-06-30T00:00:00Z",
            # reason_codes deliberately omitted -> defaults to []
        )
    except Exception:
        rejected_at_construction = True

    served_without_reasons = False
    if not rejected_at_construction:
        ALERTS.add(bad)
        # Assign to the analyst so even a case-scoped view would surface it.
        from app.store.user_store import USER_STORE

        USER_STORE.assign_alert("EMP-an01", "alr_noreason")
        r = client.get("/api/v1/alerts/alr_noreason", headers=auth("senior"))
        served_without_reasons = r.status_code == 200 and not r.json().get(
            "reason_codes"
        )

    assert rejected_at_construction or not served_without_reasons, (
        "An alert with EMPTY reason_codes was accepted by the schema/store and served by "
        "GET /alerts/{id} with HTTP 200 and no reason codes. Such an alert is not "
        "contestable (Part 29.2 / Part 16): nothing prevents an un-justified accusation "
        "from being surfaced for action."
    )


def test_block_request_is_never_auto_executed(client, auth):
    """ALERT-ONLY: a block-request must report auto_blocked=False and require approval."""
    r = client.post(
        "/api/v1/alerts/alr_demo01/block-request",
        headers=auth("senior"),
        json={"reason": "suspected mule payout"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (
        body["auto_blocked"] is False
    ), "block-request auto-blocked money (ALERT-ONLY breach)"
    assert body["requires_approval_by"] == "agm_vigilance"
