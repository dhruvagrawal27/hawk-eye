"""Real-telemetry ingestion + label-sourcing scaffold (DATA-18; Part 21.3, 5.2/5.4).

Status: SCAFFOLD. Awaits live feeds + real labelled bank fraud data (explicitly
unavailable). This module maps *real* CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR feeds into
the L0 unified event model and exposes the label-sourcing + PU/semi-supervised entry
points so that, when a live feed is plugged in (config change + creds), the same code
goes live with no rewrite.

It REUSES the synthetic mock adapters (DATA-13/14) as the per-source mapping logic:
a real feed is just a different ``read()`` source feeding the same ``to_l0`` mapping.
So the synthetic fixtures double as the contract the live feed must satisfy.

Label hooks (depends on DATA-23 label store; stubbed here so this imports standalone):
  * ``GOLD``  — gold historical Vigilance/CBI/forensic-audit case outcomes (real labels).
  * ``WEAK``  — weak/heuristic labels from Layer-1 rule hits (Snorkel-style).
  * ``EDD``   — EDD feedback (fraud/FP/inconclusive) from BACKEND disposition API.

PU / semi-supervised entry points: ``pu_positive_unlabelled_split`` partitions a
stream into (positives, unlabelled) so a PU-learning model can exploit the unlabelled
majority; ``semi_supervised_pool`` returns the labelled + unlabelled pools.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Iterator, Optional

from data.connectors.base_adapter import IngestMode, SourceAdapter
from data.connectors.cbs.adapter import CbsPostingAdapter
from data.connectors.dlp_dbaudit.adapter import DbAuditDlpAdapter
from data.connectors.hr_iga.adapter import HrIgaAdapter
from data.connectors.iam_pam.adapter import IamPamAdapter
from data.connectors.payments.adapter import PaymentsMessageAdapter
from data.schemas import L0Event


class LabelHook(str, Enum):
    """The three label channels a real feed can carry (Part 5.4)."""

    GOLD = "gold"   # real Vigilance/CBI/forensic-audit case outcomes
    WEAK = "weak"   # Layer-1 rule-hit / heuristic (Snorkel-style)
    EDD = "edd"     # EDD disposition feedback from BACKEND


# Map a real source name -> the synthetic mapping adapter that defines its to_l0.
# A live feed swaps the adapter's read() for a CDC/batch tap; to_l0 is unchanged.
def _build_source_adapters() -> dict[str, SourceAdapter]:
    return {
        "cbs": CbsPostingAdapter(),
        "swift": PaymentsMessageAdapter(rail="swift"),
        "rtgs": PaymentsMessageAdapter(rail="rtgs"),
        "neft": PaymentsMessageAdapter(rail="neft"),
        "imps": PaymentsMessageAdapter(rail="imps"),
        "upi": PaymentsMessageAdapter(rail="upi"),
        "iam": IamPamAdapter(system="iam"),
        "pam": IamPamAdapter(system="pam"),
        "vpn": IamPamAdapter(system="vpn"),
        "db": DbAuditDlpAdapter(source="db_audit"),
        "dlp": DbAuditDlpAdapter(source="dlp"),
        "hr": HrIgaAdapter(source="hr"),
        "iga": HrIgaAdapter(source="iga"),
    }


@dataclass
class RealTelemetryAdapter:
    """Routes a real source name to the right L0 mapping and exposes label hooks.

    SCAFFOLD: ``live_reader`` is the seam for a live feed — supply a callable that
    yields raw rows from the real CDC/batch/SIEM tap and ``to_l0`` runs unchanged.
    With no ``live_reader`` it falls back to the synthetic fixture (so it runs now).
    """

    source: str
    mode: IngestMode = IngestMode.CDC_STREAM
    live_reader: Optional[Callable[[], Iterable[dict[str, Any]]]] = None
    # label hook resolvers: event_id -> (is_fraud | None). None == unlabelled.
    gold_labeller: Optional[Callable[[str], Optional[bool]]] = None
    weak_labeller: Optional[Callable[[str], Optional[bool]]] = None
    edd_labeller: Optional[Callable[[str], Optional[bool]]] = None

    def __post_init__(self) -> None:
        adapters = _build_source_adapters()
        if self.source not in adapters:
            raise ValueError(
                f"unknown real-telemetry source {self.source!r}; "
                f"expected one of {sorted(adapters)}"
            )
        self._adapter = adapters[self.source]
        self._adapter.mode = self.mode

    @property
    def channel(self) -> str:
        return self._adapter.channel

    def stream(self) -> Iterator[L0Event]:
        """Yield validated L0 events. Uses the live reader if supplied, else the fixture."""
        if self.live_reader is not None:
            for raw in self.live_reader():
                yield self._adapter.to_l0(raw)
        else:
            yield from self._adapter.stream()

    # ---- label hooks (Part 5.4; depends on DATA-23 in production) -------------
    def label_for(self, event_id: str, hook: LabelHook) -> Optional[bool]:
        """Resolve a label for an event via the requested hook. None == unlabelled."""
        resolver = {
            LabelHook.GOLD: self.gold_labeller,
            LabelHook.WEAK: self.weak_labeller,
            LabelHook.EDD: self.edd_labeller,
        }[hook]
        if resolver is None:
            return None  # SCAFFOLD: no live label source wired yet
        return resolver(event_id)


# ---- PU-learning / semi-supervised entry points (Part 21.3) ------------------
def pu_positive_unlabelled_split(
    events: Iterable[L0Event],
    is_positive: Callable[[L0Event], Optional[bool]],
) -> tuple[list[L0Event], list[L0Event]]:
    """Partition events into (positives, unlabelled) for PU learning.

    PU learning treats only confirmed positives as labelled and the entire rest
    (negatives + true-but-undiscovered positives) as unlabelled — exactly the
    bank-fraud reality where only caught fraud is known. ``is_positive`` returns
    True (positive), or None/False (unlabelled).
    """
    positives: list[L0Event] = []
    unlabelled: list[L0Event] = []
    for ev in events:
        if is_positive(ev) is True:
            positives.append(ev)
        else:
            unlabelled.append(ev)
    return positives, unlabelled


def semi_supervised_pool(
    events: Iterable[L0Event],
    labeller: Callable[[L0Event], Optional[bool]],
) -> tuple[list[tuple[L0Event, bool]], list[L0Event]]:
    """Split into (labelled (event,label) pairs, unlabelled events) for semi-supervised.

    Exploits the unlabelled majority: any event the labeller returns None for goes to
    the unlabelled pool; True/False go to the labelled pool with their label.
    """
    labelled: list[tuple[L0Event, bool]] = []
    unlabelled: list[L0Event] = []
    for ev in events:
        lab = labeller(ev)
        if lab is None:
            unlabelled.append(ev)
        else:
            labelled.append((ev, bool(lab)))
    return labelled, unlabelled


# The real source families this scaffold maps (for tests / onboarding tracking).
REAL_SOURCES = (
    "cbs", "swift", "rtgs", "neft", "imps", "upi",
    "iam", "pam", "vpn", "db", "dlp", "hr", "iga",
)
