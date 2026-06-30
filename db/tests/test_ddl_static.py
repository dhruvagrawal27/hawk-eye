"""DATABASE-3/4 — static checks on the ClickHouse DDL/config (no live CH needed)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHDIR = REPO / "db" / "clickhouse"


def _read(rel: str) -> str:
    return (CHDIR / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "ddl",
    [
        "ddl/01_events.sql",
        "ddl/02_scores.sql",
        "ddl/03_alerts.sql",
        "ddl/04_dispositions.sql",
        "ddl/05_feature_backfill.sql",
        "ddl/06_reports.sql",
    ],
)
def test_each_table_has_engine_partition_order(ddl):
    text = _read(ddl)
    assert "ENGINE = ReplacingMergeTree" in text
    assert "PARTITION BY" in text
    assert "ORDER BY" in text


def test_events_order_key_prefix_and_idempotency():
    text = _read("ddl/01_events.sql")
    assert "ORDER BY (actor_employee_id, ts, event_id)" in text
    assert "ReplacingMergeTree(ingested_at)" in text  # idempotency on event_id


def test_zstd_and_delta_codecs_present():
    text = _read("ddl/01_events.sql")
    assert "CODEC(ZSTD" in text
    assert "CODEC(Delta, ZSTD" in text  # timestamp compression (Part 9.2)


def test_storage_configuration_has_hot_cold_archive_policy():
    xml = _read("storage_configuration.xml")
    assert "<cold>" in xml and "<archive>" in xml
    assert "<tiered>" in xml
    assert "<endpoint>http://minio:9001/clickhouse-cold/" in xml


def test_cluster_xml_is_sharded_replicated():
    xml = _read("cluster.xml")
    assert "hawkeye_cluster" in xml
    assert xml.count("<shard>") >= 2  # sharded
    assert "<replica>" in xml  # replicated
    assert "default_replica_path" in xml  # replicated DDL needs no explicit zk args


def test_indexes_have_inverted_and_skip_indices():
    idx = _read("indexes.sql")
    assert "TYPE full_text" in idx  # inverted/full-text
    assert "tokenbf_v1" in idx
    assert "ngrambf_v1" in idx
    assert "bloom_filter" in idx
    assert "minmax" in idx
    # investigative columns covered
    for col in (
        "actor_employee_id",
        "context_src_ip",
        "object_beneficiary_id",
        "context_session_id",
    ):
        assert col in idx, f"no skip index on {col}"


def test_search_helpers_define_investigative_views():
    sh = _read("search_helpers.sql")
    for view in (
        "search_events_by_employee",
        "search_events_by_ip",
        "search_events_by_device",
        "search_events_by_beneficiary",
        "search_events_fulltext",
        "search_alerts_fulltext",
        "entity_360_timeline",
    ):
        assert view in sh, f"missing search helper view: {view}"
    assert "{employee:String}" in sh  # parameterized views


def test_retention_ttl_matches_evidence_vs_operational():
    ttl = (REPO / "db" / "retention" / "clickhouse_ttl.sql").read_text()
    # operational expires; evidence does not
    assert re.search(r"events MODIFY TTL[\s\S]*?DELETE", ttl)
    alerts_block = re.search(r"alerts MODIFY TTL[\s\S]*?;", ttl).group(0)
    assert "DELETE" not in alerts_block, "alerts (evidence) must not auto-DELETE"
