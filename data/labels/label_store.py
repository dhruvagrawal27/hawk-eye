"""Four-source label store + PU/semi-supervised hooks (DATA-23).

Blueprint Part 5.4 (l.196-201) + Part 21.3 (l.813-815). Overall status: MOCK
(source 1 is seeded fixtures; source 4 depends on a not-yet-built BACKEND endpoint).

The four sources (Part 5.4):
  1. GOLD historical  -- Vigilance/CBI/forensic-audit outcomes. MOCK seeded fixtures;
     real labelled bank fraud is unavailable.
  2. WEAK / heuristic  -- Layer-1 rule hits as programmatic (Snorkel-style) labels.
     `snorkel` is OPTIONAL -> guarded import with a pure-python majority-vote fallback.
  3. SYNTHETIC         -- red-team injection ground truth (DATA-10 Label objects).
  4. EDD feedback      -- fraud/false_positive/inconclusive dispositions ingested from
     BACKEND `POST /alerts/{id}/disposition` (BACKEND.md §5). SCAFFOLD/STUB until the
     BACKEND endpoint exists; we already match the §5 payload shape exactly.

Labels are kept SEPARATE from L0 events (leakage avoidance, Part 21.4): the store keys
everything by `event_id` and emits `data.schemas.label.Label` objects.

PU-learning / semi-supervised entry points (Part 5.4 / 21.3) exploit the vast unlabelled
majority: `pu_reliable_negatives` (spy-style reliable-negative selection) and
`self_training_pseudolabels` (confidence-thresholded self-training).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence

from data.schemas.label import Label

# BACKEND.md §5: disposition outcome -> fraud truth value.
EDD_OUTCOME_TO_FRAUD: dict[str, Optional[bool]] = {
    "fraud": True,
    "false_positive": False,
    "inconclusive": None,   # no firm label -> stays in the unlabelled pool for PU
}

# Source precedence when the same event_id has multiple labels (highest wins).
_SOURCE_PRIORITY = {"edd": 4, "gold": 3, "synthetic": 2, "weak": 1}


# --------------------------------------------------------------------------- #
# Weak labelling (source 2): Snorkel-optional, pure-python fallback            #
# --------------------------------------------------------------------------- #
@dataclass
class LabelingFunction:
    """A weak labelling function (Snorkel-style). Returns 1 (fraud), 0 (benign),
    or -1 (abstain) for an event dict."""
    name: str
    fn: Callable[[dict], int]

    def __call__(self, event: dict) -> int:
        try:
            return int(self.fn(event))
        except Exception:
            return -1  # abstain on error


def _apply_label_matrix(lfs: Sequence[LabelingFunction],
                        events: Sequence[dict]) -> list[list[int]]:
    return [[lf(ev) for lf in lfs] for ev in events]


def weak_label_events(
    lfs: Sequence[LabelingFunction], events: Sequence[dict]
) -> list[tuple[int, float]]:
    """Aggregate weak labelling functions into (label, confidence) per event.

    Uses Snorkel's LabelModel when available; otherwise a pure-python majority vote
    over non-abstaining votes (confidence = winning fraction). Both ignore -1 abstains.
    """
    L = _apply_label_matrix(lfs, events)
    try:  # OPTIONAL snorkel path
        import numpy as _np
        from snorkel.labeling.model import LabelModel  # type: ignore

        Lm = _np.array(L)
        model = LabelModel(cardinality=2, verbose=False)
        model.fit(Lm, n_epochs=50, seed=1405)
        probs = model.predict_proba(Lm)
        preds = probs.argmax(axis=1)
        conf = probs.max(axis=1)
        return [(int(p), float(c)) for p, c in zip(preds, conf)]
    except Exception:
        # pure-python majority-vote fallback
        out: list[tuple[int, float]] = []
        for votes in L:
            cast = [v for v in votes if v in (0, 1)]
            if not cast:
                out.append((-1, 0.0))
                continue
            pos = sum(1 for v in cast if v == 1)
            neg = len(cast) - pos
            if pos == neg:
                out.append((-1, 0.5))
            elif pos > neg:
                out.append((1, pos / len(cast)))
            else:
                out.append((0, neg / len(cast)))
        return out


# --------------------------------------------------------------------------- #
# The label store                                                             #
# --------------------------------------------------------------------------- #
class LabelStore:
    """Unifies the four label sources, keyed by event_id, emitting Label objects."""

    def __init__(self) -> None:
        # event_id -> {source: Label}
        self._labels: dict[str, dict[str, Label]] = defaultdict(dict)

    # ---- source 1: GOLD historical (MOCK seeded fixtures) -------------------
    def add_gold_fixtures(self, fixtures: Optional[Iterable[dict]] = None) -> int:
        """Seed gold historical positives (Vigilance/CBI/forensic). MOCK.

        Each fixture: {event_id, actor_id?, scenario_id?, ring_id?, lane?}.
        Defaults to a small built-in seed set when none supplied.
        """
        if fixtures is None:
            fixtures = self._default_gold_fixtures()
        n = 0
        for fx in fixtures:
            lab = Label(
                event_id=fx["event_id"], is_fraud=True,
                scenario_id=fx.get("scenario_id", "historical_case"),
                actor_id=fx.get("actor_id"), ring_id=fx.get("ring_id"),
                lane=fx.get("lane", "slow"), label_source="gold", confidence=1.0,
            )
            self._labels[lab.event_id]["gold"] = lab
            n += 1
        return n

    @staticmethod
    def _default_gold_fixtures() -> list[dict]:
        # MOCK: stand-ins for forensic-audit confirmed cases (synthetic ids only).
        return [
            {"event_id": "evt_gold0001", "actor_id": "EMP-9a01",
             "scenario_id": "swift_without_cbs", "lane": "fast"},
            {"event_id": "evt_gold0002", "actor_id": "EMP-9a02",
             "scenario_id": "ghost_vendor", "ring_id": "RNG-0007", "lane": "slow"},
        ]

    # ---- source 2: WEAK / heuristic (rule hits, Snorkel-style) ---------------
    def add_weak_labels(
        self, lfs: Sequence[LabelingFunction], events: Sequence[dict]
    ) -> int:
        """Apply labelling functions (Layer-1 rule-hit heuristics) to events."""
        results = weak_label_events(lfs, events)
        n = 0
        for ev, (lab, conf) in zip(events, results):
            if lab not in (0, 1):
                continue  # abstain -> leave unlabelled (PU pool)
            eid = ev.get("event_id")
            if not eid:
                continue
            self._labels[eid]["weak"] = Label(
                event_id=eid, is_fraud=bool(lab),
                actor_id=(ev.get("actor") or {}).get("employee_id"),
                label_source="weak", confidence=float(conf),
            )
            n += 1
        return n

    @staticmethod
    def default_labeling_functions() -> list[LabelingFunction]:
        """A couple of Layer-1-style rule heuristics as weak labellers."""
        def lf_offhours_highvalue(ev: dict) -> int:
            ctx = ev.get("context") or {}
            obj = ev.get("object") or {}
            amt = obj.get("amount") or 0
            if ctx.get("is_off_hours") and amt and amt >= 1_000_000:
                return 1
            return -1  # abstain (not enough signal) rather than assert benign

        def lf_leaver_export(ev: dict) -> int:
            actor = ev.get("actor") or {}
            verb = (ev.get("action") or {}).get("verb")
            if actor.get("notice_period") and verb in ("export", "usb"):
                return 1
            return -1

        return [
            LabelingFunction("offhours_highvalue", lf_offhours_highvalue),
            LabelingFunction("leaver_export", lf_leaver_export),
        ]

    # ---- source 3: SYNTHETIC red-team (DATA-10 Label objects) ----------------
    def add_synthetic_labels(self, labels: Iterable[Label]) -> int:
        n = 0
        for lab in labels:
            lab.label_source = "synthetic"
            self._labels[lab.event_id]["synthetic"] = lab
            n += 1
        return n

    # ---- source 4: EDD feedback (BACKEND.md §5) -- STUB until endpoint lands --
    def ingest_edd_disposition(self, payload: dict) -> Optional[Label]:
        """Ingest a BACKEND `POST /alerts/{id}/disposition` payload (BACKEND.md §5).

        Expected request shape:
            {"outcome": "fraud"|"false_positive"|"inconclusive",
             "notes": str, "evidence_ids": [event_id, ...], "alert_id": "alr_..."}

        Writes a Label per evidence event_id. `inconclusive` writes NO label (the event
        stays in the unlabelled PU pool). Returns the first Label written (or None).

        SCAFFOLD: until BACKEND-EDD-DISPOSITION-API is live, callers feed the §5 fixture.
        """
        outcome = payload.get("outcome")
        if outcome not in EDD_OUTCOME_TO_FRAUD:
            raise ValueError(
                f"unknown disposition outcome {outcome!r}; expected one of "
                f"{sorted(EDD_OUTCOME_TO_FRAUD)} (BACKEND.md §5)"
            )
        is_fraud = EDD_OUTCOME_TO_FRAUD[outcome]
        if is_fraud is None:
            return None  # inconclusive -> no label written
        evidence = payload.get("evidence_ids") or []
        alert_id = payload.get("alert_id")
        first: Optional[Label] = None
        for eid in evidence:
            lab = Label(
                event_id=eid, is_fraud=is_fraud,
                scenario_id=f"edd:{alert_id}" if alert_id else "edd",
                label_source="edd", confidence=1.0,
            )
            self._labels[eid]["edd"] = lab
            if first is None:
                first = lab
        return first

    @staticmethod
    def edd_response_fixture(alert_id: str = "alr_3d7e22") -> dict:
        """The BACKEND.md §5 RESPONSE shape (stub until the real endpoint exists)."""
        return {
            "alert_id": alert_id, "status": "confirmed_fraud", "label_written": True,
            "feedback_queued_for_retraining": True, "audit_id": "aud_99f0c1",
        }

    # ---- merge / read -------------------------------------------------------
    def merge(self) -> list[Label]:
        """Resolve to one Label per event_id by source precedence (edd>gold>synthetic>weak)."""
        out: list[Label] = []
        for eid, by_src in self._labels.items():
            best_src = max(by_src, key=lambda s: _SOURCE_PRIORITY.get(s, 0))
            out.append(by_src[best_src])
        return sorted(out, key=lambda l: l.event_id)

    def sources_present(self) -> set[str]:
        s: set[str] = set()
        for by_src in self._labels.values():
            s.update(by_src.keys())
        return s

    def get(self, event_id: str) -> Optional[Label]:
        by_src = self._labels.get(event_id)
        if not by_src:
            return None
        best_src = max(by_src, key=lambda s: _SOURCE_PRIORITY.get(s, 0))
        return by_src[best_src]

    def labelled_event_ids(self) -> set[str]:
        return set(self._labels.keys())


# --------------------------------------------------------------------------- #
# PU-learning / semi-supervised entry points (Part 5.4 / 21.3)                #
# --------------------------------------------------------------------------- #
def pu_reliable_negatives(
    all_event_ids: Iterable[str],
    positive_ids: Iterable[str],
    scores: Optional[dict[str, float]] = None,
    negative_fraction: float = 0.3,
) -> list[str]:
    """PU-learning hook: pick RELIABLE NEGATIVES from the unlabelled majority.

    In Positive-Unlabelled learning we only have positives (P) and unlabelled (U) data.
    Reliable negatives are the unlabelled events LEAST similar to the positives. With a
    `scores` map (e.g. a model's fraud-probability per event), we take the lowest-scoring
    fraction of U as reliable negatives; without scores we fall back to a deterministic
    prefix of U so the hook is always usable. Returns event_ids to treat as negatives.
    """
    pos = set(positive_ids)
    unlabelled = [e for e in all_event_ids if e not in pos]
    if not unlabelled:
        return []
    k = max(1, int(round(len(unlabelled) * negative_fraction)))
    if scores:
        unlabelled.sort(key=lambda e: scores.get(e, 0.0))  # lowest fraud-score first
    else:
        unlabelled.sort()  # deterministic
    return unlabelled[:k]


def self_training_pseudolabels(
    scores: dict[str, float],
    labelled_ids: Iterable[str],
    high: float = 0.9,
    low: float = 0.1,
) -> dict[str, bool]:
    """Semi-supervised hook: confidence-thresholded self-training pseudo-labels.

    For currently-unlabelled events, assign a pseudo-label only when the model is
    confident: score >= `high` -> fraud (True); score <= `low` -> benign (False);
    everything in between stays unlabelled. Returns {event_id: is_fraud}.
    """
    labelled = set(labelled_ids)
    out: dict[str, bool] = {}
    for eid, sc in scores.items():
        if eid in labelled:
            continue
        if sc >= high:
            out[eid] = True
        elif sc <= low:
            out[eid] = False
    return out


def demo_store() -> LabelStore:
    """Build a tiny store populated from all four sources, for tests."""
    store = LabelStore()
    store.add_gold_fixtures()
    store.add_synthetic_labels([
        Label(event_id="evt_syn0001", is_fraud=True, scenario_id="beneficiary_then_approve",
              actor_id="EMP-1234", lane="fast"),
    ])
    events = [
        {"event_id": "evt_weak0001",
         "actor": {"employee_id": "EMP-5678", "notice_period": True},
         "action": {"verb": "export"}, "object": {}, "context": {}},
    ]
    store.add_weak_labels(store.default_labeling_functions(), events)
    store.ingest_edd_disposition({
        "alert_id": "alr_3d7e22", "outcome": "fraud",
        "notes": "Confirmed shell beneficiary; maker-checker collusion.",
        "evidence_ids": ["evt_8f2a1c90"],
    })
    return store
