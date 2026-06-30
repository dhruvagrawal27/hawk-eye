"""Governance tests (DATA-2/6/25/26/27). Plain test_* functions, bare assert.

Runnable by data/tests/run.py (pytest is not installed). Each test builds tiny inputs
or calls a module demo helper and asserts behaviour.
"""
from __future__ import annotations

import copy

import pandas as pd

from data.schemas import AVRO_SCHEMA


# ---- DATA-2: schema registry compatibility ---------------------------------
def test_registry_rejects_field_removal():
    from data.registry.schema_registry import (
        SchemaRegistry, Compatibility, is_compatible, register_l0,
    )

    reg = register_l0(SchemaRegistry(compatibility=Compatibility.BACKWARD))
    subject = "events.raw-value"

    # Removing a required field (event_id) from the top-level record -> breaking.
    broken = copy.deepcopy(AVRO_SCHEMA)
    broken["fields"] = [f for f in broken["fields"] if f["name"] != "event_id"]
    ok, reasons = is_compatible(AVRO_SCHEMA, broken)
    assert ok is False
    assert any("event_id" in r for r in reasons)

    raised = False
    try:
        reg.register(subject, broken)
    except ValueError:
        raised = True
    assert raised, "registry must reject a BACKWARD-incompatible field removal"


def test_registry_accepts_additive_change():
    from data.registry.schema_registry import (
        SchemaRegistry, Compatibility, is_compatible, register_l0,
    )

    reg = register_l0(SchemaRegistry(compatibility=Compatibility.BACKWARD))
    subject = "events.raw-value"

    additive = copy.deepcopy(AVRO_SCHEMA)
    # Add an OPTIONAL field (union with null + default) -> compatible.
    additive["fields"].append(
        {"name": "ingest_source", "type": ["null", "string"], "default": None}
    )
    ok, reasons = is_compatible(AVRO_SCHEMA, additive)
    assert ok is True, f"additive optional field should be compatible: {reasons}"

    version = reg.register(subject, additive)
    assert version == 2, "additive change should register as the next version"


# ---- DATA-26: classification -----------------------------------------------
def test_classification_tags_pii_and_sensitive():
    from data.governance.classification import classification_map, Tag

    cm = classification_map()
    # employee_id is PII; account_id is PAN (an account-number, the most-restrictive
    # 'sensitive' class for masking).
    assert cm["actor.employee_id"] == Tag.PII
    assert cm["object.account_id"] == Tag.PAN
    # every documented field is classified
    from data.governance.catalog.dictionary import all_field_paths
    for path in all_field_paths():
        assert path in cm


def test_dictionary_documents_every_l0_field():
    from data.governance.catalog.dictionary import all_field_paths

    paths = set(all_field_paths())
    # spot-check one field from each of the five groups + top-level
    for expected in ("event_id", "actor.employee_id", "action.verb",
                     "object.amount", "context.is_off_hours", "linkage.swift_ref"):
        assert expected in paths


# ---- DATA-27: data quality + retention -------------------------------------
def test_quality_check_catches_null_in_required_field():
    from data.governance.quality.expectations import check, _demo_good_df, _demo_corrupt_df

    good = check(_demo_good_df())
    assert good.passed, f"clean fixture should pass: {good.to_dashboard()}"

    corrupt = check(_demo_corrupt_df())
    assert not corrupt.passed, "corrupted fixture (null required field) must be caught"
    cats = {f.category for f in corrupt.failures}
    assert "completeness" in cats
    dash = corrupt.to_dashboard()
    assert dash["failed"] >= 1


def test_retention_erasure_carve_out():
    from data.governance.retention import erase, apply_lifecycle, _demo_records

    records = _demo_records()
    surviving, res = erase(records, "EMP-aaaa")
    # the ops record is erased; the under-investigation record is withheld (carve-out)
    assert "r-ops" in res.erased
    assert "r-case" in res.withheld
    assert res.reason["r-case"] == "active_investigation"

    # lifecycle deletion also respects the carve-out
    _, life = apply_lifecycle(records)
    assert "r-ops" in life.deleted
    assert "r-case" in life.carved_out


# ---- DATA-25: lineage -------------------------------------------------------
def test_lineage_records_stable_content_hash():
    from data.lineage.lineage import (
        LineageGraph, content_hash, record_training_lineage, link_alert,
    )

    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    h1 = content_hash(df)
    h2 = content_hash(df.copy())
    assert h1 == h2, "same data -> same content hash"

    df2 = df.copy()
    df2.loc[0, "a"] = 99
    assert content_hash(df2) != h1, "a changed cell must change the hash"

    g = LineageGraph()
    pinned = record_training_lineage(
        g, source_id="source:events.raw", dataset=df,
        feature_names=["offhours_score", "amount_zscore"], model_id="model:l3_xgb",
    )
    assert pinned["dataset_hash"] == h1
    assert pinned["feature_set_version"].startswith("fsv_")

    link_alert(g, "model:l3_xgb", "alert:alr_1")
    # full source->feature->model->alert lineage: alert traces back to the source
    anc = g.ancestors("alert:alr_1")
    assert "source:events.raw" in anc


# ---- DATA-26: MDM entity resolution ----------------------------------------
def test_entity_resolution_merges_same_person():
    from data.mdm.entity_resolution import resolve, _demo_records

    resolved = resolve(_demo_records())
    # the HR/IAM/CBS records for the same person merge into ONE entity (transitively via
    # shared employee_id and national_id_token); the unrelated person is separate.
    by_size = sorted(resolved, key=lambda e: -len(e.records))
    merged = by_size[0]
    assert len(merged.records) == 3
    assert merged.sources == {"hr", "iam", "cbs"}
    # exactly two resolved entities total
    assert len(resolved) == 2


# ---- DATA-6: feature store parity (one definition, online + offline) -------
def test_feature_store_online_offline_parity():
    from data.feature_store import build_repo, OnlineStore

    repo = build_repo()
    store = OnlineStore()  # dict fallback (no live redis needed)

    # offline frame keyed by employee_id with the SAME columns the view reads
    offline = pd.DataFrame([
        {"employee_id": "EMP-7f3a", "offhours_event_count_30d": 5,
         "txn_amount_zscore": 2.1, "new_beneficiary_count_7d": 1},
    ])
    hist = repo.get_historical_features(offline, "employee_risk")
    assert "txn_amount_zscore" in hist.columns

    n = repo.materialize(offline, "employee_risk", store)
    assert n == 1
    online_val = store.read_feature("employee", "EMP-7f3a", "txn_amount_zscore")
    # online value equals the offline value -> single-definition parity
    assert abs(float(online_val) - 2.1) < 1e-9
