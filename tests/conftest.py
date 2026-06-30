"""Shared pytest path setup for the platform test harness (PLATFORM-16/21).

Adds the platform tool + service roots to sys.path so unit/contract/integration
tests can import them without packaging. Each laptop adds its own tests under
tests/<ws>/; this conftest only wires PLATFORM-owned import roots.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (
    ROOT / "tools" / "sizing",
    ROOT / "tools" / "staffing-calculator",
    ROOT / "tools" / "finops",
    ROOT / "tools" / "override-fatigue",
    ROOT / "tools" / "release",
    ROOT / "ops" / "capacity",
    ROOT / "services" / "degradation-switch",
    ROOT / "services" / "tee-attestation",
    ROOT / "services" / "pam-shim",
    ROOT / "services" / "governance-api",
    ROOT / "services" / "hitl-gate",
    ROOT / "governance" / "db",
    ROOT / "governance" / "go-live",
    ROOT / "governance" / "rbac",
    ROOT / "governance" / "validation",
    ROOT / "security" / "vuln-mgmt",
):
    sys.path.insert(0, str(p))
