"""Management analytics store — fraud-typology prevalence + confirmed-rate.

Aggregates the alert/disposition population by fraud typology (the `scenario_id` a synthetic red-team
scenario maps to), so oversight can see *which insider typologies are actually firing*, how often
they're confirmed vs cleared, and the exposure behind each. Seeded with a plausible synthetic
portfolio (the 12 typologies + their detection layers per docs/detection-coverage-map.md); the live
lane would compute this from `hawkeye.alerts` ⋈ `hawkeye.dispositions`. Honest, synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TypologyRow:
    typology: str
    label: str
    layers: list[str]
    alerts: int
    confirmed: int
    false_positive: int
    exposure_inr: int

    @property
    def open(self) -> int:
        return max(0, self.alerts - self.confirmed - self.false_positive)

    @property
    def confirmed_rate(self) -> float:
        denom = self.confirmed + self.false_positive
        return round(self.confirmed / denom, 4) if denom else 0.0


class AnalyticsStore:
    def __init__(self) -> None:
        self._rows: list[TypologyRow] = []

    def reset(self) -> None:
        self._rows = []

    def set_rows(self, rows: list[TypologyRow]) -> None:
        self._rows = rows

    def typology_snapshot(self) -> dict:
        rows = sorted(self._rows, key=lambda r: r.alerts, reverse=True)
        typologies = [
            {
                "typology": r.typology,
                "label": r.label,
                "layers": r.layers,
                "alerts": r.alerts,
                "confirmed": r.confirmed,
                "false_positive": r.false_positive,
                "open": r.open,
                "confirmed_rate": r.confirmed_rate,
                "exposure_inr": r.exposure_inr,
            }
            for r in rows
        ]
        alerts = sum(r.alerts for r in rows)
        confirmed = sum(r.confirmed for r in rows)
        fp = sum(r.false_positive for r in rows)
        opened = sum(r.open for r in rows)
        denom = confirmed + fp
        return {
            "typologies": typologies,
            "totals": {
                "alerts": alerts,
                "confirmed": confirmed,
                "false_positive": fp,
                "open": opened,
                "confirmed_rate": round(confirmed / denom, 4) if denom else 0.0,
                "exposure_inr": sum(r.exposure_inr for r in rows),
            },
        }


ANALYTICS = AnalyticsStore()

# (typology, label, layers, alerts, confirmed, false_positive, exposure_inr)
_SEED: tuple[tuple[str, str, list[str], int, int, int, int], ...] = (
    ("beneficiary_then_approve", "New-beneficiary → high-value approve", ["L1", "L3", "L5"], 38, 9, 21, 54_800_000),
    ("maker_checker_ring", "Maker-checker collusion ring", ["L5"], 27, 11, 9, 41_200_000),
    ("bulk_exfil_resignation", "Bulk exfil in leaver window", ["L2", "L4"], 24, 7, 13, 3_100_000),
    ("alert_suppression", "AML alert suppression", ["L2", "L3"], 22, 5, 14, 0),
    ("dormant_takeover", "Dormant-account takeover", ["L1", "L2"], 19, 6, 10, 12_600_000),
    ("privilege_self_grant", "Entitlement self-grant", ["L1"], 17, 8, 6, 0),
    ("fake_vendor", "Fake-vendor / billing", ["L1", "L3", "L5"], 15, 4, 9, 28_400_000),
    ("swift_without_cbs", "SWIFT without CBS recon", ["L1"], 12, 5, 4, 96_000_000),
    ("rogue_trader", "Rogue trading", ["L2", "L4"], 11, 3, 6, 74_500_000),
    ("ghost_employee_payroll", "Ghost employee / payroll", ["L1", "L3", "L5"], 9, 3, 5, 6_800_000),
    ("suspense_lapping", "Suspense / nostro lapping", ["L2"], 8, 2, 5, 9_300_000),
    ("ghost_loan_appraisal", "Inflated loan appraisal", ["L3"], 6, 2, 3, 33_000_000),
)


def seed_analytics() -> None:
    """Idempotent demo seed of the typology portfolio (reseeded on every seed_demo call)."""
    ANALYTICS.set_rows(
        [
            TypologyRow(
                typology=t, label=label, layers=layers, alerts=a,
                confirmed=c, false_positive=fp, exposure_inr=exp,
            )
            for (t, label, layers, a, c, fp, exp) in _SEED
        ]
    )
