"""pandas-3.0 forward-compat regression tests.

pandas 3.0 makes string columns the extension `StringDtype` (not `object`), which
`np.issubdtype(series.dtype, ...)` cannot interpret. We force a `string`-dtype column
(reproduces the failure on pandas 2.x AND 3.0) and assert the split helpers still work.
Regression guard for the `_sortable` fix in data/datasets/splits.py.
"""
from __future__ import annotations

import pandas as pd

from data.datasets.splits import (
    temporal_split,
    is_temporal_split,
    assert_not_random_split,
    make_random_split,
    detect_leaky_features,
    remove_leaky_features,
)


def _string_dtype_frame() -> pd.DataFrame:
    """A frame whose ts column is the pandas extension StringDtype (the pd-3.0 default)."""
    ts = pd.date_range("2026-01-01", periods=60, freq="h").astype(str)
    return pd.DataFrame({
        "ts": pd.array(list(ts), dtype="string"),      # <-- extension StringDtype on every pandas
        "entity": pd.array([f"EMP-{i % 6}" for i in range(60)], dtype="string"),
        "amount": range(60),
        "leaky": [i % 2 for i in range(60)],
        "label": [i % 2 for i in range(60)],
    })


def test_temporal_split_handles_string_extension_dtype():
    df = _string_dtype_frame()
    assert str(df["ts"].dtype) in ("string", "str")  # extension dtype, not object
    train, test = temporal_split(df, "ts", test_frac=0.25)
    assert len(train) and len(test)
    assert is_temporal_split(train, test, "ts")


def test_random_split_rejected_with_string_dtype():
    df = _string_dtype_frame()
    rtr, rte = make_random_split(df)
    raised = False
    try:
        assert_not_random_split(rtr, rte, "ts")
    except AssertionError:
        raised = True
    assert raised, "random split should be rejected even with string-dtype ts"


def test_leaky_detection_with_string_dtype_columns():
    df = _string_dtype_frame()
    leaks = detect_leaky_features(df, "label")
    assert "leaky" in leaks
    assert "leaky" not in remove_leaky_features(df, "label").columns
