"""M2.3 — PAM session-content command parser + session analyzer."""

from __future__ import annotations

from data.connectors.iam_pam.command_parser import CommandParser
from data.features.pam_session import SessionCommandAnalyzer

P = CommandParser()


def test_mass_select_export_detected():
    c = P.parse("SELECT * FROM customer_pii INTO OUTFILE '/tmp/x.csv'")
    assert c.kind == "sql" and c.is_export
    assert "customer_pii" in c.tables_touched


def test_update_extracts_table_not_export():
    c = P.parse("UPDATE accounts SET balance = 0 WHERE id = 5")
    assert c.kind == "sql" and c.verb == "update"
    assert c.tables_touched == ["accounts"] and not c.is_export


def test_drop_is_ddl_and_destructive():
    c = P.parse("DROP TABLE audit_log")
    assert c.is_ddl and c.is_destructive and "audit_log" in c.tables_touched


def test_os_dump_is_export():
    assert P.parse("mysqldump governance > /tmp/g.sql").is_export
    assert P.parse("scp dump.tar user@host:/x").is_export


def test_os_destructive_and_config():
    assert P.parse("drop_database governance").is_destructive
    assert P.parse("rotate_secret NEAR_AI_API_KEY").is_config_change


def test_limit_rowcount_parsed():
    assert P.parse("select id from t limit 50000").rowcount == 50000


def test_empty_command_safe():
    c = P.parse("")
    assert c.kind == "unknown" and c.verb == ""


def test_analyzer_aggregates_session():
    cmds = [
        "SELECT * FROM customer_pii",       # mass export
        "DROP TABLE audit_log",             # ddl 1
        "ALTER TABLE accounts ADD c int",   # ddl 2
        "GRANT ALL ON accounts TO bob",     # ddl 3 + config
        "login",                            # noise
    ]
    f = SessionCommandAnalyzer().analyze("sess-1", cmds)
    assert f.command_velocity == 5
    assert f.mass_select_export is True
    assert f.ddl_chain >= 3
    assert f.config_change is True
    feats = f.to_features()
    assert feats["pam_mass_select_export"] and feats["pam_ddl_chain"] >= 3


def test_analyzer_caches_per_session():
    a = SessionCommandAnalyzer()
    first = a.analyze("s", ["SELECT * FROM t"])
    second = a.analyze("s", ["totally different"])  # cached → same result
    assert first is second
