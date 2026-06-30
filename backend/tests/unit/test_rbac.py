"""RBAC 8×9 matrix + SoD enforcement unit tests (BACKEND-3)."""

from __future__ import annotations

import pytest

from app.auth import rbac, sod
from app.auth.principal import Principal
from app.schemas.common import Capability, Role


def test_matrix_is_8_by_9():
    assert len(rbac.MATRIX) == 8
    for role, row in rbac.MATRIX.items():
        assert len(row) == 9, role


@pytest.mark.parametrize(
    "role,cap,allowed",
    [
        (Role.ANALYST, Capability.DISPOSITION, True),
        (Role.ANALYST, Capability.TUNE_RULES, False),
        (Role.ANALYST, Capability.TRAIN_DEPLOY_MODELS, False),
        (Role.ANALYST, Capability.VIEW_AUDIT, False),
        (Role.COMPLIANCE_OFFICER, Capability.TUNE_RULES, True),
        (Role.COMPLIANCE_OFFICER, Capability.DISPOSITION, False),
        (Role.AUDITOR, Capability.VIEW_AUDIT, True),
        (Role.AUDITOR, Capability.DISPOSITION, False),
        (Role.MODEL_ENGINEER, Capability.TRAIN_DEPLOY_MODELS, True),
        (Role.MODEL_ENGINEER, Capability.DISPOSITION, False),
        (Role.MODEL_ENGINEER, Capability.UNMASK_PII, False),
        (Role.PLATFORM_ADMIN, Capability.ADMIN, True),
        (Role.PLATFORM_ADMIN, Capability.VIEW_ALERTS, False),
        (Role.SENIOR_INVESTIGATOR, Capability.UNMASK_PII, True),
    ],
)
def test_matrix_cells(role, cap, allowed):
    assert rbac.is_allowed(role, cap) is allowed


def test_unmask_is_separate_from_view():
    # Auditor can view alerts (read-only) but cannot unmask PII — a separate, audited capability.
    assert rbac.is_allowed(Role.AUDITOR, Capability.VIEW_ALERTS)
    assert not rbac.is_allowed(Role.AUDITOR, Capability.UNMASK_PII)


def test_sod_deployer_cannot_label():
    me = Principal(user_id="EMP-me01", role=Role.MODEL_ENGINEER)
    with pytest.raises(sod.SoDError):
        sod.check_disposition(me, alert_owner=None, subject_entity="EMP-7f3a")


def test_sod_no_self_review():
    analyst = Principal(user_id="EMP-7f3a", role=Role.ANALYST)
    with pytest.raises(sod.SoDError):
        sod.check_disposition(analyst, alert_owner=None, subject_entity="EMP-7f3a")


def test_sod_four_eyes():
    with pytest.raises(sod.SoDError):
        sod.check_four_eyes("EMP-co01", "EMP-co01")
    sod.check_four_eyes("EMP-co01", "EMP-tl01")  # ok, distinct


def test_sod_promotion_signoff_distinct():
    with pytest.raises(sod.SoDError):
        sod.check_promotion_signoff("EMP-me01", "EMP-me01")
    sod.check_promotion_signoff("EMP-me01", "EMP-tl01")  # ok


def test_sod_investigator_cannot_tune_own_alert_rules():
    analyst = Principal(user_id="EMP-an01", role=Role.ANALYST, assigned_alerts={"alr_1"})
    with pytest.raises(sod.SoDError):
        sod.check_rule_tuning(analyst, generated_alerts={"alr_1"})
