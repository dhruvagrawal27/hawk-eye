"""Source-onboarding status tracker (DATA-17, Part 32.3).

Tracks each source through the 8 playbook stages (see data/docs/source_onboarding_playbook.md)
and exposes a dashboard view for the program dashboard. REAL (pure-python).
"""
from __future__ import annotations

from dataclasses import dataclass, field

STAGES = [
    "discovery", "schema_mapping", "connector_build", "dq_rules",
    "backfill", "lineage_validation", "shadow", "promote",
]

# Initial source inventory (DATA-13/14/18). Most are SCAFFOLD until live feeds + creds.
DEFAULT_SOURCES = {
    "cbs": "slow", "payments": "fast", "iam_ad": "fast", "pam": "fast", "vpn": "fast",
    "db_audit": "fast", "dlp": "fast", "hr_hrms": "slow", "iga": "slow",
}


@dataclass
class SourceOnboarding:
    source: str
    lane: str = "fast"
    stage: str = "discovery"
    status: str = "scaffold"   # scaffold | live

    def advance(self, exit_criterion_passed: bool) -> str:
        """Move to the next stage iff the current stage's exit criterion passed."""
        if not exit_criterion_passed:
            return self.stage
        i = STAGES.index(self.stage)
        if i < len(STAGES) - 1:
            self.stage = STAGES[i + 1]
        if self.stage == "promote":
            self.status = "live" if exit_criterion_passed else "scaffold"
        return self.stage


@dataclass
class OnboardingRegistry:
    sources: dict[str, SourceOnboarding] = field(default_factory=dict)

    @classmethod
    def with_defaults(cls) -> "OnboardingRegistry":
        reg = cls()
        for src, lane in DEFAULT_SOURCES.items():
            reg.sources[src] = SourceOnboarding(source=src, lane=lane)
        return reg

    def dashboard(self) -> list[dict]:
        """Program-dashboard view: per-source stage + status."""
        return [
            {"source": s.source, "lane": s.lane, "stage": s.stage, "status": s.status,
             "stage_index": STAGES.index(s.stage), "stages_total": len(STAGES)}
            for s in self.sources.values()
        ]
