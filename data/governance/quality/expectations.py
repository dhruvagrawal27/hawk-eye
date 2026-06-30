"""Data-quality expectations + validation suite (DATA-27).

Blueprint Part 28.2 (data quality, l.1204), Part 28.1 (l.1197), Part 31.1 (data
validation tests: schema conformance, range/null, freshness, distribution, l.1261).
Status: REAL.

Great Expectations / Pandera are OPTIONAL. This module implements the SAME validation
categories in pure pandas so the suite runs with only numpy/pandas/pyarrow:
  - completeness   : required columns present and non-null above a threshold.
  - validity       : values match a pattern / allowed set (e.g. event_id ~ ^evt_,
                     ts ends in 'Z', currency in a small set).
  - schema conform : all expected columns exist (no missing/renamed required column).
  - range/null     : numeric ranges (amount >= 0) and explicit null checks on keys.
  - freshness      : max event age within an SLA (silent-feed-loss guard).
  - distribution   : a column's value distribution stays within configured bounds
                     (e.g. off-hours fraction not wildly out of range).

``check()`` runs the suite on a (flattened) L0 DataFrame and returns a ``CheckResult``
with a DQ-dashboard hook (``to_dashboard()``); it CATCHES a corrupted fixture (a null in
a required field), satisfying the DATA-27 acceptance check.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import pandas as pd

# ---- optional GE / Pandera (decision logic stays pure-python either way) -----
try:  # pragma: no cover
    import great_expectations  # type: ignore  # noqa: F401

    _HAVE_GE = True
except Exception:  # pragma: no cover
    _HAVE_GE = False


@dataclass
class Expectation:
    """One named expectation: a predicate over a DataFrame returning (passed, detail)."""

    name: str
    category: str  # completeness | validity | schema | range_null | freshness | distribution
    fn: Callable[[pd.DataFrame], tuple[bool, str]]

    def run(self, df: pd.DataFrame) -> "ExpectationOutcome":
        try:
            passed, detail = self.fn(df)
        except Exception as exc:  # a failing predicate is a failed expectation
            return ExpectationOutcome(self.name, self.category, False, f"error: {exc}")
        return ExpectationOutcome(self.name, self.category, passed, detail)


@dataclass
class ExpectationOutcome:
    name: str
    category: str
    passed: bool
    detail: str


@dataclass
class CheckResult:
    outcomes: list[ExpectationOutcome] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(o.passed for o in self.outcomes)

    @property
    def failures(self) -> list[ExpectationOutcome]:
        return [o for o in self.outcomes if not o.passed]

    def to_dashboard(self) -> dict[str, Any]:
        """DQ-dashboard hook (Part 28.2 DQ SLAs + dashboard)."""
        total = len(self.outcomes)
        passed = sum(1 for o in self.outcomes if o.passed)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": (passed / total) if total else 1.0,
            "failures": [{"name": o.name, "category": o.category, "detail": o.detail}
                         for o in self.failures],
        }


@dataclass
class ExpectationSuite:
    name: str
    expectations: list[Expectation] = field(default_factory=list)

    def add(self, exp: Expectation) -> "ExpectationSuite":
        self.expectations.append(exp)
        return self

    def run(self, df: pd.DataFrame) -> CheckResult:
        return CheckResult([e.run(df) for e in self.expectations])


# ---- predicate builders -----------------------------------------------------
_EVT_RE = re.compile(r"^evt_")
_ALLOWED_CURRENCIES = {"INR", "USD", "EUR", "GBP", None}


def _required_non_null(cols: list[str]) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        missing_cols = [c for c in cols if c not in df.columns]
        if missing_cols:
            return False, f"missing required columns: {missing_cols}"
        nulls = {c: int(df[c].isna().sum()) for c in cols if df[c].isna().any()}
        if nulls:
            return False, f"nulls in required columns: {nulls}"
        return True, "all required columns present and non-null"
    return _f


def _columns_present(cols: list[str]) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        missing = [c for c in cols if c not in df.columns]
        if missing:
            return False, f"schema non-conformant: missing columns {missing}"
        return True, "schema conformant"
    return _f


def _matches_pattern(col: str, rx: re.Pattern[str]) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        if col not in df.columns:
            return False, f"column '{col}' absent"
        bad = df[~df[col].astype(str).str.match(rx)]
        if len(bad):
            return False, f"{len(bad)} value(s) in '{col}' fail pattern {rx.pattern}"
        return True, f"all '{col}' values match {rx.pattern}"
    return _f


def _ts_ends_z(col: str) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        if col not in df.columns:
            return False, f"column '{col}' absent"
        bad = df[~df[col].astype(str).str.endswith("Z")]
        if len(bad):
            return False, f"{len(bad)} '{col}' value(s) not UTC ISO-8601 ('...Z')"
        return True, f"all '{col}' values are UTC ISO-8601"
    return _f


def _in_set(col: str, allowed: set[Any]) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        if col not in df.columns:
            return True, f"column '{col}' absent (skipped)"
        bad = df[~df[col].isin(allowed)]
        if len(bad):
            return False, f"{len(bad)} '{col}' value(s) outside allowed set"
        return True, f"all '{col}' values in allowed set"
    return _f


def _non_negative(col: str) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        if col not in df.columns:
            return True, f"column '{col}' absent (skipped)"
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        bad = vals[vals < 0]
        if len(bad):
            return False, f"{len(bad)} negative value(s) in '{col}'"
        return True, f"'{col}' values non-negative"
    return _f


def _freshness(col: str, max_age_seconds: float) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        if col not in df.columns or df.empty:
            return False, f"no timestamps to assess freshness in '{col}'"
        ts = pd.to_datetime(df[col], errors="coerce", utc=True).dropna()
        if ts.empty:
            return False, f"unparseable timestamps in '{col}'"
        now = datetime.now(timezone.utc)
        oldest_age = (now - ts.min().to_pydatetime()).total_seconds()
        if oldest_age > max_age_seconds:
            return False, f"stale data: oldest event {oldest_age:.0f}s old > SLA {max_age_seconds:.0f}s"
        return True, f"data fresh (oldest {oldest_age:.0f}s)"
    return _f


def _distribution_fraction(
    col: str, value: Any, lo: float, hi: float
) -> Callable[[pd.DataFrame], tuple[bool, str]]:
    def _f(df: pd.DataFrame) -> tuple[bool, str]:
        if col not in df.columns or df.empty:
            return True, f"column '{col}' absent/empty (skipped)"
        frac = float((df[col] == value).mean())
        if not (lo <= frac <= hi):
            return False, f"distribution drift: '{col}=={value}' fraction {frac:.3f} outside [{lo},{hi}]"
        return True, f"'{col}=={value}' fraction {frac:.3f} within [{lo},{hi}]"
    return _f


# ---- the L0 ingestion expectation suite -------------------------------------
# Operates on FLATTENED L0 rows (dotted column names, as ParquetSink emits).
REQUIRED_COLUMNS = [
    "event_id", "ts", "actor.employee_id", "action.verb",
]


def l0_expectation_suite(
    *,
    freshness_sla_seconds: float = 365 * 24 * 3600.0,
    offhours_bounds: tuple[float, float] = (0.0, 1.0),
) -> ExpectationSuite:
    """Build the L0 ingestion validation suite (all six categories).

    ``freshness_sla_seconds`` defaults to a generous 1y so synthetic batches with
    historical timestamps pass; tighten it for live feeds. ``offhours_bounds`` lets a
    caller assert the off-hours distribution stays plausible.
    """
    suite = ExpectationSuite("l0_ingestion")
    # completeness + range/null on required keys
    suite.add(Expectation("required_fields_complete", "completeness",
                          _required_non_null(REQUIRED_COLUMNS)))
    # schema conformance
    suite.add(Expectation("schema_conformance", "schema",
                          _columns_present(REQUIRED_COLUMNS)))
    # validity
    suite.add(Expectation("event_id_pattern", "validity",
                          _matches_pattern("event_id", _EVT_RE)))
    suite.add(Expectation("ts_utc_iso", "validity", _ts_ends_z("ts")))
    suite.add(Expectation("currency_allowed", "validity",
                          _in_set("object.currency", _ALLOWED_CURRENCIES)))
    # range / null
    suite.add(Expectation("amount_non_negative", "range_null",
                          _non_negative("object.amount")))
    # freshness
    suite.add(Expectation("freshness_sla", "freshness",
                          _freshness("ts", freshness_sla_seconds)))
    # distribution
    suite.add(Expectation("offhours_distribution", "distribution",
                          _distribution_fraction("context.is_off_hours", True,
                                                 offhours_bounds[0], offhours_bounds[1])))
    return suite


def check(df: pd.DataFrame, suite: Optional[ExpectationSuite] = None) -> CheckResult:
    """Run the L0 expectation suite over a flattened L0 DataFrame."""
    suite = suite or l0_expectation_suite()
    return suite.run(df)


def _demo_good_df() -> pd.DataFrame:
    from data.schemas import SAMPLE_EVENT
    from data.eventbus import ParquetSink

    row = ParquetSink._flatten(SAMPLE_EVENT)
    return pd.DataFrame([row, {**row, "event_id": "evt_aaaa1111"}])


def _demo_corrupt_df() -> pd.DataFrame:
    """A deliberately-corrupted fixture: null in a required field (actor.employee_id)."""
    df = _demo_good_df()
    df.loc[0, "actor.employee_id"] = None
    return df
