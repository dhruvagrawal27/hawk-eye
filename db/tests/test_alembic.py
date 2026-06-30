"""DATABASE-2 — Alembic migrations: single head + offline upgrade/downgrade render."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

alembic = pytest.importorskip("alembic")
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO / "db" / "postgres" / "migrations"


def _config() -> Config:
    cfg = Config(str(REPO / "db" / "postgres" / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS))
    return cfg


@pytest.fixture(autouse=True)
def _dummy_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/hawkeye"
    )


def test_single_head():
    heads = ScriptDirectory.from_config(_config()).get_heads()
    assert len(heads) == 1, f"expected exactly one Alembic head, got {heads}"


def test_offline_upgrade_renders_all_tables():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        command.upgrade(_config(), "head", sql=True)
    sql = buf.getvalue()
    for table in (
        "hawkeye.users",
        "hawkeye.cases",
        "hawkeye.case_notes",
        "hawkeye.case_history",
        "hawkeye.alerts_metadata",
        "hawkeye.model_governance",
        "hawkeye.approvals",
        "hawkeye.pii_vault",
    ):
        assert f"CREATE TABLE {table}" in sql, f"upgrade missing {table}"
    # least-privilege roles
    for role in ("hawkeye_migrate", "hawkeye_app", "hawkeye_ro"):
        assert role in sql
    # pii_vault read REVOKED from the read-only role
    assert "REVOKE ALL ON hawkeye.pii_vault FROM hawkeye_ro" in sql


def test_offline_downgrade_is_reversible():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        # offline --sql needs an explicit start:end range (no DB to read current rev)
        command.downgrade(_config(), "head:base", sql=True)  # raises if not reversible
    sql = buf.getvalue()
    assert "DROP TABLE hawkeye.users" in sql
    assert "DROP ROLE IF EXISTS hawkeye_app" in sql
