"""Alert persistence (BACKEND-19): with HAWKEYE_DB_URL set, alerts survive a restart and reload into
the in-memory query cache. Default (no URL) stays purely in-memory.

Imports are done inside the tests so this module doesn't perturb the package import order at
collection time (the app has a pre-existing user_store↔oidc import cycle that the normal
app.main entrypoint resolves)."""

from __future__ import annotations

# Load the app first so app.auth.oidc is imported before the autouse _reset fixture pulls
# app.store.user_store (the codebase has a user_store↔oidc import cycle the app entrypoint resolves).
import app.main  # noqa: F401, E402


def _alert(aid: str = "alr_persist"):
    from app.schemas.alerts import Alert

    return Alert(
        alert_id=aid,
        entity_id="EMP-x",
        risk_score=71,
        severity="high",
        confidence=0.8,
        status="open",
        created_ts="2026-07-01T00:00:00Z",
        contributing_layers=["L1_rules", "L3_gbdt"],
        reason_codes=[{"source": "rule", "detail": "off-hours, just under threshold"}],
        exposure_inr=4_800_000,
        pii_tokenized=True,
    )


def test_no_db_url_disables_persistence() -> None:
    from app.store.persistence import make_backend

    assert make_backend("") is None


def test_alerts_survive_restart(tmp_path) -> None:  # noqa: ANN001 - pytest fixture
    from app.store.alert_store import PersistedAlertStore
    from app.store.persistence import make_backend

    db = str(tmp_path / "alerts.db")

    store1 = PersistedAlertStore(make_backend(f"sqlite:///{db}"))
    store1.add(_alert("alr_persist"))
    store1.assign("alr_persist", "EMP-tl01")
    store1.set_status("alr_persist", "confirmed_fraud")

    # "restart": a brand-new store object over the same durable file
    store2 = PersistedAlertStore(make_backend(f"sqlite:///{db}"))
    got = store2.get("alr_persist")
    assert got is not None
    assert got.alert_id == "alr_persist"
    assert got.risk_score == 71
    assert str(got.status) == "confirmed_fraud"
    assert got.assignee == "EMP-tl01"
    items, total = store2.query(limit=10)
    assert total == 1 and items[0].alert_id == "alr_persist"
