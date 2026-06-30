"""Peer-fair, alert-only scoring design + the simple-beats-deep decision summary (ML-9)."""

from __future__ import annotations

from ml.design.alert_only_contract import (
    ALLOWED_ADVISORY_ACTIONS,
    FORBIDDEN_AUTONOMOUS_ACTIONS,
    Advisory,
    AlertOnlyViolation,
    alert_only_contract,
    assert_advisory_action,
)
from ml.design.peer_fair import (
    PeerRelativeScorer,
    peer_group_from_features,
    peer_relative_scores,
    peer_relative_unit,
)

__all__ = [
    "Advisory",
    "AlertOnlyViolation",
    "alert_only_contract",
    "assert_advisory_action",
    "ALLOWED_ADVISORY_ACTIONS",
    "FORBIDDEN_AUTONOMOUS_ACTIONS",
    "PeerRelativeScorer",
    "peer_relative_scores",
    "peer_relative_unit",
    "peer_group_from_features",
]
