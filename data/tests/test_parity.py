"""DATA-22 train/serve-skew parity test (Part 6 engineering note).

Proves the acceptance criterion: the SAME feature definition (one FeatureView) yields the
SAME value via the OFFLINE retrieval path (`get_historical_features`) and the ONLINE serving
path (`materialize` -> `OnlineStore.read_feature`). Same input -> same online and offline value.
"""
from __future__ import annotations

import pandas as pd

from data.feature_store.feature_repo.repo import Entity, Feature, FeatureView, FeatureRepo
from data.feature_store.online_store import OnlineStore
from data.features.transaction import amount_zscore


def _entity_feature_frame() -> pd.DataFrame:
    """Compute a real feature (amount z-score, max per entity) OFFLINE from raw events."""
    df = pd.DataFrame({
        "actor.employee_id": ["EMP-1", "EMP-1", "EMP-2", "EMP-2", "EMP-2"],
        "object.amount": [1000, 9000, 500, 600, 700],
        "context.ts": ["2026-01-01T01:00:00Z", "2026-01-01T02:00:00Z",
                       "2026-01-01T03:00:00Z", "2026-01-01T04:00:00Z", "2026-01-01T05:00:00Z"],
    })
    z = amount_zscore(df, scope="personal")
    df = df.assign(amount_z=z.values)
    # latest row per entity (what materialize stores online)
    per = df.groupby("actor.employee_id", as_index=False).agg(amount_z=("amount_z", "last"))
    return per.rename(columns={"actor.employee_id": "employee_id"})


def _repo() -> tuple[FeatureRepo, str]:
    emp = Entity(name="employee", join_key="employee_id")
    view = FeatureView(
        name="txn_features",
        entity=emp,
        features=(Feature(name="amount_z", dtype="float", source_column="amount_z"),),
    )
    return FeatureRepo().apply(emp, view), "txn_features"


def test_online_equals_offline_parity():
    feature_df = _entity_feature_frame()
    repo, view = _repo()
    store = OnlineStore()

    # ONLINE path: materialize -> read back from the online store
    written = repo.materialize(feature_df, view, store)
    assert written == len(feature_df)

    # OFFLINE path: historical retrieval over the same entities + same view
    offline = repo.get_historical_features(feature_df, view).set_index("employee_id")["amount_z"]

    for emp_id, off_val in offline.items():
        online_val = store.read_feature("employee", str(emp_id), "amount_z")
        assert online_val is not None, f"online store missing {emp_id}"
        assert abs(float(online_val) - float(off_val)) < 1e-9, (
            f"parity broken for {emp_id}: online={online_val} offline={off_val}"
        )


def test_feature_definition_is_single_source():
    """The same FeatureView object backs both paths (no duplicate definition)."""
    repo, view = _repo()
    v = repo.get_view(view)
    assert [f.name for f in v.features] == ["amount_z"]
    assert v.entity.join_key == "employee_id"
