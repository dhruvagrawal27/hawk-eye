"""DATABASE-2 integration — Postgres schema/roles (live) + Redis DB0/DB1.

Requires the storage compose up (postgres + pg-migrate applied; redis).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def pg():
    psycopg2 = pytest.importorskip("psycopg2")
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "hawkeye"),
            password=os.getenv("POSTGRES_PASSWORD", "hawkeye_dev_pw"),
            dbname=os.getenv("POSTGRES_DB", "hawkeye"),
        )
    except Exception as exc:  # pragma: no cover - infra dependent
        pytest.skip(f"Postgres not reachable: {exc}")
    yield conn
    conn.close()


def test_schema_tables_exist(pg):
    cur = pg.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='hawkeye'"
    )
    tables = {r[0] for r in cur.fetchall()}
    expected = {
        "users",
        "cases",
        "case_notes",
        "case_history",
        "alerts_metadata",
        "model_governance",
        "approvals",
        "pii_vault",
    }
    missing = expected - tables
    assert not missing, f"missing tables (did pg-migrate run?): {missing}"


def test_least_privilege_roles_exist(pg):
    cur = pg.cursor()
    cur.execute("SELECT rolname FROM pg_roles WHERE rolname LIKE 'hawkeye_%'")
    roles = {r[0] for r in cur.fetchall()}
    assert {"hawkeye_migrate", "hawkeye_app", "hawkeye_ro"} <= roles


def test_pii_vault_read_revoked_from_readonly(pg):
    cur = pg.cursor()
    # hawkeye_ro must NOT have SELECT on pii_vault (need-to-know; unmask is audited)
    cur.execute(
        "SELECT has_table_privilege('hawkeye_ro', 'hawkeye.pii_vault', 'SELECT')"
    )
    assert cur.fetchone()[0] is False
    # hawkeye_app DOES (BACKEND write/read path)
    cur.execute(
        "SELECT has_table_privilege('hawkeye_app', 'hawkeye.pii_vault', 'INSERT')"
    )
    assert cur.fetchone()[0] is True


def test_redis_db0_online_db1_cache():
    redis = pytest.importorskip("redis")
    try:
        r0 = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=6379,
            db=0,
            password=os.getenv("REDIS_PASSWORD", "hawkeye_dev_pw"),
        )
        r0.ping()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Redis not reachable: {exc}")
    # DB0 online feature key convention "<entity>:<feature>:<window>"
    r0.set("EMP-7f3a:offhours_score:30d", "0.91")
    assert r0.get("EMP-7f3a:offhours_score:30d") == b"0.91"
    r1 = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=6379,
        db=1,
        password=os.getenv("REDIS_PASSWORD", "hawkeye_dev_pw"),
    )
    r1.set("cache:test", "1", ex=60)
    assert r1.get("cache:test") == b"1"
    r0.delete("EMP-7f3a:offhours_score:30d")
    r1.delete("cache:test")
