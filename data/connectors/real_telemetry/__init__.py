"""Real-telemetry ingestion + label-sourcing scaffold (DATA-18). SCAFFOLD: awaits
live feeds + real labels. Maps real CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR -> L0 with
gold/weak/EDD label hooks + PU/semi-supervised entry points."""
from data.connectors.real_telemetry.adapter import (  # noqa: F401
    REAL_SOURCES,
    LabelHook,
    RealTelemetryAdapter,
    pu_positive_unlabelled_split,
    semi_supervised_pool,
)

__all__ = [
    "RealTelemetryAdapter", "LabelHook", "REAL_SOURCES",
    "pu_positive_unlabelled_split", "semi_supervised_pool",
]
