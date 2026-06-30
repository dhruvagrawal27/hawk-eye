"""FeatureSource adapter: the seam between ML and DATA (ML-1; prompt §3, §5).

ML consumes DATA's L0 events + feature catalogue. This adapter hides whether the
rows come from the real simulator output (``data/out/<run>/``), a freshly-run
DATA simulator, or a self-contained synthetic fixture — the rest of ``ml/`` only
sees ``event_features()`` / ``entity_features()`` / labels.

# STUB: DATA/DATABASE — when the real Feast online store + ClickHouse offline
# tables land, add a ``FeastFeatureSource`` here with the same interface and swap.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.adapters import featurize
from ml.config.seeds import GLOBAL_SEED

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FeatureSource(ABC):
    """Interface every feature source implements. Subclasses provide events()+labels()."""

    @abstractmethod
    def events(self) -> pd.DataFrame:
        """Flattened L0 events (dotted column names)."""

    @abstractmethod
    def labels(self) -> pd.DataFrame:
        """Labels keyed by event_id (is_fraud, scenario_id, actor_id, lane, ...)."""

    # --- shared, derived from events()+labels() via the common featuriser --- #
    def event_features(self) -> pd.DataFrame:
        return featurize.event_level_features(self.events())

    def entity_features(self) -> pd.DataFrame:
        return featurize.entity_level_features(self.events())

    def event_labels(self) -> pd.Series:
        return featurize.join_event_labels(self.event_features(), self.labels())

    def entity_labels(self) -> pd.Series:
        return featurize.entity_labels(self.events(), self.labels())

    def supervised_xy(self) -> tuple[pd.DataFrame, pd.Series]:
        """(event feature matrix, 0/1 fraud label) for L3-style supervised training."""
        X = self.event_features()
        y = self.event_labels()
        return X, y

    def unsupervised_x(self) -> pd.DataFrame:
        """Per-entity feature matrix for L2 UEBA."""
        return self.entity_features()

    def online_features(self, entity_id: str) -> dict[str, Any]:
        """Latest per-entity feature vector (online-serving lookup)."""
        ef = self.entity_features()
        if entity_id in ef.index:
            return {k: float(v) for k, v in ef.loc[entity_id].to_dict().items()}
        return {}


class DataSimFeatureSource(FeatureSource):
    """Real DATA simulator output. Loads an existing run dir, else generates one.

    Falls back to the in-process synthetic generator if the DATA package or its
    deps are unavailable, so ML tests never hard-depend on DATA being importable.
    """

    def __init__(
        self,
        run_dir: Optional[str] = None,
        *,
        employees: int = 150,
        days: int = 10,
        seed: int = GLOBAL_SEED,
    ) -> None:
        self._events: Optional[pd.DataFrame] = None
        self._labels: Optional[pd.DataFrame] = None
        self.employees = employees
        self.days = days
        self.seed = seed
        self.run_dir = run_dir or self._discover_run_dir()

    @staticmethod
    def _discover_run_dir() -> Optional[str]:
        out = os.path.join(REPO_ROOT, "data", "out")
        if not os.path.isdir(out):
            return None
        runs = [
            os.path.join(out, d)
            for d in os.listdir(out)
            if os.path.isfile(os.path.join(out, d, "events.parquet"))
        ]
        return sorted(runs)[-1] if runs else None

    def _load(self) -> None:
        if self._events is not None:
            return
        if self.run_dir and os.path.isfile(os.path.join(self.run_dir, "events.parquet")):
            self._events = pd.read_parquet(os.path.join(self.run_dir, "events.parquet"))
            self._labels = pd.read_parquet(os.path.join(self.run_dir, "labels.parquet"))
            return
        # Try to generate via the real DATA simulator.
        try:  # pragma: no cover - exercised only when no run dir exists
            import sys

            if REPO_ROOT not in sys.path:
                sys.path.insert(0, REPO_ROOT)
            from data.config import SimConfig  # type: ignore
            from data.sim import Simulator  # type: ignore

            sim = Simulator(SimConfig(n_employees=self.employees, days=self.days, seed=self.seed))
            ev, lab = sim.run_records()
            self._events = _flatten_events(ev)
            self._labels = pd.DataFrame(lab)
            return
        except Exception:
            fallback = SyntheticFeatureSource(seed=self.seed)
            self._events, self._labels = fallback.events(), fallback.labels()

    def events(self) -> pd.DataFrame:
        self._load()
        assert self._events is not None
        return self._events

    def labels(self) -> pd.DataFrame:
        self._load()
        assert self._labels is not None
        return self._labels


class SyntheticFeatureSource(FeatureSource):
    """Self-contained synthetic L0 generator (no DATA dependency) for unit tests.

    Produces normal behaviour plus injected fraud bursts (new-beneficiary->high-value
    approval off-hours, bulk export by leavers) so behavioural/directional tests have
    clear separable signal. Output columns match the flattened L0 schema.
    """

    DEPTS = ("trade_finance", "retail_ops", "treasury", "it_admin", "payments")
    ROLES = ("ops_maker", "ops_checker", "analyst", "dba", "trader")

    def __init__(
        self,
        n_employees: int = 60,
        n_days: int = 7,
        fraud_rate: float = 0.12,
        seed: int = GLOBAL_SEED,
    ) -> None:
        self.n_employees = n_employees
        self.n_days = n_days
        self.fraud_rate = fraud_rate
        self.seed = seed
        self._events: Optional[pd.DataFrame] = None
        self._labels: Optional[pd.DataFrame] = None

    def _generate(self) -> None:
        if self._events is not None:
            return
        rng = np.random.default_rng(self.seed)
        n_fraud = max(1, int(self.n_employees * self.fraud_rate))
        fraud_ids = set(range(n_fraud))
        ev_rows: list[dict] = []
        lab_rows: list[dict] = []
        eid = 0
        base = pd.Timestamp("2026-06-01T00:00:00Z")

        for emp_i in range(self.n_employees):
            emp = f"EMP-{emp_i:04d}"
            dept = self.DEPTS[emp_i % len(self.DEPTS)]
            role = self.ROLES[emp_i % len(self.ROLES)]
            peer = f"PG-{dept}"
            tenure = int(rng.integers(120, 4000))
            privileged = role in ("dba", "ops_checker")
            is_fraud_actor = emp_i in fraud_ids
            leaver = is_fraud_actor and rng.random() < 0.5

            for day in range(self.n_days):
                n_normal = int(rng.integers(4, 12))
                for _ in range(n_normal):
                    hour = int(rng.integers(9, 18))
                    ts = base + pd.Timedelta(days=day, hours=hour, minutes=int(rng.integers(0, 59)))
                    verb = rng.choice(["login", "approve_payment", "db_select", "create_beneficiary"])
                    amount = float(rng.integers(1000, 80000)) if verb == "approve_payment" else None
                    ev_rows.append(
                        _event_row(eid, emp, role, dept, peer, tenure, privileged, leaver, ts,
                                   verb=str(verb), amount=amount, off_hours=False)
                    )
                    lab_rows.append(_label_row(eid, False, None, None, None))
                    eid += 1

            if is_fraud_actor:
                # Injected fraud burst: new beneficiary off-hours, then high-value approval.
                bene = f"BEN-{emp_i:04d}"
                t0 = base + pd.Timedelta(days=int(rng.integers(1, self.n_days)), hours=2)
                ev_rows.append(
                    _event_row(eid, emp, role, dept, peer, tenure, privileged, leaver, t0,
                               verb="create_beneficiary", bene=bene, off_hours=True, maker="maker")
                )
                lab_rows.append(_label_row(eid, True, "beneficiary_then_approve", emp, "fast"))
                eid += 1
                ev_rows.append(
                    _event_row(eid, emp, role, dept, peer, tenure, privileged, leaver,
                               t0 + pd.Timedelta(minutes=20), verb="approve_payment", bene=bene,
                               amount=4800000.0, off_hours=True, maker="checker")
                )
                lab_rows.append(_label_row(eid, True, "beneficiary_then_approve", emp, "fast"))
                eid += 1
                if leaver:
                    for _ in range(3):
                        ev_rows.append(
                            _event_row(eid, emp, role, dept, peer, tenure, privileged, leaver,
                                       t0 + pd.Timedelta(hours=1), verb="export", off_hours=True, layer="database")
                        )
                        lab_rows.append(_label_row(eid, True, "bulk_exfil_resignation", emp, "fast"))
                        eid += 1

        self._events = pd.DataFrame(ev_rows)
        self._labels = pd.DataFrame(lab_rows)

    def events(self) -> pd.DataFrame:
        self._generate()
        assert self._events is not None
        return self._events

    def labels(self) -> pd.DataFrame:
        self._generate()
        assert self._labels is not None
        return self._labels


# --------------------------------------------------------------------------- #
# row builders (produce the flattened L0 column names)                        #
# --------------------------------------------------------------------------- #
def _event_row(
    eid: int,
    emp: str,
    role: str,
    dept: str,
    peer: str,
    tenure: int,
    privileged: bool,
    leaver: bool,
    ts: pd.Timestamp,
    *,
    verb: str = "login",
    channel: str = "cbs",
    amount: Optional[float] = None,
    bene: str = "",
    off_hours: bool = False,
    maker: str = "",
    layer: str = "application",
) -> dict:
    tss = pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "event_id": f"evt_{eid:08d}",
        "ts": tss,
        "actor.employee_id": emp,
        "actor.role": role,
        "actor.dept": dept,
        "actor.branch": f"BR-{(hash(emp) % 50):03d}",
        "actor.tenure_days": tenure,
        "actor.manager_id": "EMP-9999",
        "actor.peer_group": peer,
        "actor.privileged_flag": privileged,
        "actor.leaver_flag": leaver,
        "actor.notice_period": leaver,
        "action.verb": verb,
        "action.channel": channel,
        "action.maker_checker": maker,
        "object.account_id": f"ACCT-{(eid % 1000):04d}",
        "object.beneficiary_id": bene,
        "object.table": "",
        "object.entitlement_id": "",
        "object.instrument": "",
        "object.amount": amount,
        "object.currency": "INR",
        "context.ts": tss,
        "context.src_ip": "10.20.4.31",
        "context.device": f"WS-{(eid % 200):03d}",
        "context.geo": "Mumbai",
        "context.session_id": f"sess_{eid % 9999:04d}",
        "context.layer": layer,
        "context.is_off_hours": off_hours,
        "context.host": "",
        "linkage.swift_ref": "",
        "linkage.cbs_ref": "",
        "linkage.app_txn_id": "" if layer == "database" else f"txn_{eid}",
        "linkage.db_write_id": f"dbw_{eid}" if layer == "database" else "",
        "linkage.maker_id": emp if maker else "",
        "linkage.checker_id": "",
        "linkage.customer_account": f"ACCT-{(eid % 1000):04d}",
    }


def _label_row(
    eid: int,
    is_fraud: bool,
    scenario_id: Optional[str],
    actor_id: Optional[str],
    lane: Optional[str],
) -> dict:
    return {
        "event_id": f"evt_{eid:08d}",
        "is_fraud": is_fraud,
        "scenario_id": scenario_id,
        "actor_id": actor_id,
        "ring_id": None,
        "lane": lane,
        "label_source": "synthetic",
        "confidence": 1.0,
    }


def _flatten_events(event_dicts: list[dict]) -> pd.DataFrame:
    """Flatten nested L0 event dicts (from data.sim) into dotted columns."""
    rows = []
    for e in event_dicts:
        row = {"event_id": e.get("event_id"), "ts": e.get("ts")}
        for group in ("actor", "action", "object", "context", "linkage"):
            for k, v in (e.get(group) or {}).items():
                row[f"{group}.{k}"] = v
        rows.append(row)
    return pd.DataFrame(rows)
