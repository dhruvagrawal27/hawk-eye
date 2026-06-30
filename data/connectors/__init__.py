"""Source connectors (DATA-13/14/15/18; Part 5.2, 32.1, 9.1, 21.3).

Status: SCAFFOLD. Per-source adapters read synthetic mock fixtures into the L0
unified event model now; live feeds (CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR) need real
credentials and swap in via a config change.

DATA OWNS the adapters + mock fixtures (seam 5.7); PLATFORM owns the integration
runtime/hosting. Connectors are read-only and ALERT-ONLY (never block/enforce).
"""
from data.connectors.base_adapter import (  # noqa: F401
    CHANNELS,
    IngestMode,
    ReadOnlyCollector,
    SourceAdapter,
)

__all__ = ["CHANNELS", "IngestMode", "ReadOnlyCollector", "SourceAdapter"]
