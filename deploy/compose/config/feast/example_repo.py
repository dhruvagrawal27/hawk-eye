"""Placeholder Feast feature repo (PLATFORM host stub).

DATA (DATA-6) replaces this with the real feature views over the L0 event model.
This minimal entity + feature view exists only so `feast apply` succeeds and the
Feast server comes up green for the walking skeleton (§3 stub rule).
"""
from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64

employee = Entity(name="employee", join_keys=["employee_id"])

# A trivial file source so `feast apply` has a registerable view. DATA swaps this
# for the ClickHouse/Feast-materialized features (single train/serve definition).
_src = FileSource(path="/feature_repo/data/placeholder.parquet", timestamp_field="event_ts")

employee_features = FeatureView(
    name="employee_behaviour_placeholder",
    entities=[employee],
    ttl=timedelta(days=30),
    schema=[
        Field(name="txn_count_1h", dtype=Int64),
        Field(name="amount_zscore_peer", dtype=Float32),
    ],
    source=_src,
    online=True,
)
