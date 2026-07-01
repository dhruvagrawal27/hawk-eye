"""Shared test fixtures (BACKEND §8).

Resets the in-memory stores + reseeds before each test so tests are isolated, and provides a
``TestClient`` (with lifespan) plus a per-role auth-header helper. Cleans up any rule YAML files a
four-eyes rule-change test persisted, restoring the engine to its committed state.
"""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

# Seeded synthetic users (one per role) — password is the synthetic dev secret. The friendly keys
# are test labels, not role enum values; they resolve to the FROZEN bank-org-chart personas /
# legacy login aliases in docs/BANK_ROLES.md (e.g. EMP-tl01 → agm_vigilance, EMP-an01 →
# relationship_manager) so the existing A→Z flow and call sites stay green.
ROLE_USER = {
    # legacy labels → new roles via the old→new mapping (kept so existing tests don't churn)
    "analyst": "EMP-an01",  # relationship_manager
    "senior": "EMP-sr01",  # branch_manager
    "lead": "EMP-tl01",  # agm_vigilance (fraud-function lead / MLRO)
    "compliance": "EMP-co01",  # dgm_compliance
    "compliance2": "EMP-co02",  # dgm_compliance (second person for four-eyes)
    "auditor": "EMP-au01",  # chief_internal_auditor
    "model_engineer": "EMP-me01",  # data_science_lead
    "admin": "EMP-pa01",  # it_admin
    "service": "svc-ingest",  # service_account
    # canonical bank-org-chart personas (top-of-chart first) — including the 4 new roles
    "relationship_manager": "EMP-rm01",
    "branch_manager": "EMP-bm01",
    "cluster_head": "EMP-ch01",
    "agm_vigilance": "EMP-agm1",
    "dgm_compliance": "EMP-dgm1",
    "data_science_lead": "EMP-ds01",
    "cgm_risk": "EMP-cgm1",
    "chief_internal_auditor": "EMP-cia1",
    "executive_director": "EMP-ed01",
    "managing_director": "EMP-md01",
    "it_admin": "EMP-it01",
}
DEV_PASSWORD = "hawk-eye"

_RULES_DIR = pathlib.Path(__file__).resolve().parents[1] / "rules_engine" / "rules"
_KEEP_RULE_FILES = {"rules.yaml", "sod_matrix.yaml"}


def _clean_persisted_rules() -> None:
    for f in _RULES_DIR.glob("*.yaml"):
        if f.name not in _KEEP_RULE_FILES:
            f.unlink(missing_ok=True)


def _reset_state() -> None:
    from app.audit.writer import AUDIT
    from app.schemas.common import Role
    from app.store.alert_store import ALERTS
    from app.store.entity_store import ENTITIES
    from app.store.rule_change_store import RULE_CHANGES
    from app.store.seed import seed_demo
    from app.store.user_store import USER_STORE
    from reliability.degradation import DEGRADATION
    from reliability.idempotency import DEDUPE
    from rules_engine.engine import DEFAULT_ENGINE

    ALERTS._alerts.clear()
    ALERTS._dispositions.clear()
    ALERTS._block_requests.clear()
    ALERTS._narrative_memos.clear()
    ALERTS._feedback_queue.clear()
    ENTITIES._profiles.clear()
    ENTITIES._timelines.clear()
    ENTITIES._graphs.clear()
    ENTITIES._peers.clear()
    ENTITIES._risk_index.clear()
    RULE_CHANGES._proposals.clear()
    AUDIT._events.clear()
    DEDUPE.reset()
    DEGRADATION.recover()
    for u in USER_STORE.list():
        if u.role == Role.RELATIONSHIP_MANAGER:
            u.assigned_alerts.clear()
    _clean_persisted_rules()
    DEFAULT_ENGINE.reload()
    seed_demo()


@pytest.fixture(autouse=True)
def _reset():
    _reset_state()
    yield
    _clean_persisted_rules()


@pytest.fixture()
def client(_reset):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    """Return a function: role-name → Authorization headers for that seeded user."""

    def _auth(role: str) -> dict:
        user_id = ROLE_USER[role]
        resp = client.post(
            "/api/v1/auth/login", json={"username": user_id, "password": DEV_PASSWORD}
        )
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _auth
