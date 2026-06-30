"""RBAC 12×9 matrix + SoD enforcement unit tests (BACKEND-3, FROZEN roles docs/BANK_ROLES.md)."""

from __future__ import annotations

import pytest

from app.auth import rbac, sod
from app.auth.principal import Principal
from app.schemas.common import Capability, Role


def test_matrix_is_12_by_9():
    assert len(rbac.MATRIX) == 12
    for role, row in rbac.MATRIX.items():
        assert len(row) == 9, role


def test_all_12_roles_present():
    # Every console/RBAC role in the FROZEN spec is encoded in the matrix.
    assert set(rbac.MATRIX) == set(Role)
    assert len(Role) == 12


@pytest.mark.parametrize(
    "role,cap,allowed",
    [
        (Role.RELATIONSHIP_MANAGER, Capability.DISPOSITION, True),
        (Role.RELATIONSHIP_MANAGER, Capability.TUNE_RULES, False),
        (Role.RELATIONSHIP_MANAGER, Capability.TRAIN_DEPLOY_MODELS, False),
        (Role.RELATIONSHIP_MANAGER, Capability.VIEW_AUDIT, False),
        (Role.DGM_COMPLIANCE, Capability.TUNE_RULES, True),
        (Role.DGM_COMPLIANCE, Capability.DISPOSITION, False),
        (Role.CHIEF_INTERNAL_AUDITOR, Capability.VIEW_AUDIT, True),
        (Role.CHIEF_INTERNAL_AUDITOR, Capability.DISPOSITION, False),
        (Role.DATA_SCIENCE_LEAD, Capability.TRAIN_DEPLOY_MODELS, True),
        (Role.DATA_SCIENCE_LEAD, Capability.DISPOSITION, False),
        (Role.DATA_SCIENCE_LEAD, Capability.UNMASK_PII, False),
        (Role.IT_ADMIN, Capability.ADMIN, True),
        (Role.IT_ADMIN, Capability.VIEW_ALERTS, False),
        (Role.BRANCH_MANAGER, Capability.UNMASK_PII, True),
        # The 4 new roles (cluster_head, cgm_risk, executive_director, managing_director):
        (Role.CLUSTER_HEAD, Capability.DISPOSITION, True),  # ⚠️ override
        (Role.CLUSTER_HEAD, Capability.REQUEST_BLOCK, True),  # ⚠️ approve
        (Role.CLUSTER_HEAD, Capability.TUNE_RULES, True),  # ⚠️ propose_only
        (Role.CLUSTER_HEAD, Capability.VIEW_AUDIT, True),
        (Role.CGM_RISK, Capability.VIEW_AUDIT, True),
        (Role.CGM_RISK, Capability.TUNE_RULES, True),  # ⚠️ change_controlled
        (Role.CGM_RISK, Capability.DISPOSITION, False),
        (Role.CGM_RISK, Capability.UNMASK_PII, False),
        (Role.EXECUTIVE_DIRECTOR, Capability.VIEW_AUDIT, True),
        (Role.EXECUTIVE_DIRECTOR, Capability.DISPOSITION, False),
        (Role.EXECUTIVE_DIRECTOR, Capability.UNMASK_PII, False),
        (Role.MANAGING_DIRECTOR, Capability.VIEW_AUDIT, True),
        (Role.MANAGING_DIRECTOR, Capability.DISPOSITION, False),
        (Role.MANAGING_DIRECTOR, Capability.ADMIN, False),
    ],
)
def test_matrix_cells(role, cap, allowed):
    assert rbac.is_allowed(role, cap) is allowed


def test_exec_and_board_see_de_identified_only():
    # CGM/ED/MD and Data Science see de-identified aggregates only: view is CONDITIONAL
    # (de_identified_only), and they never get a plain ALLOW on view_alerts.
    for role in (
        Role.CGM_RISK,
        Role.EXECUTIVE_DIRECTOR,
        Role.MANAGING_DIRECTOR,
        Role.DATA_SCIENCE_LEAD,
    ):
        grant = rbac.decision(role, Capability.VIEW_ALERTS)
        assert grant.permitted
        assert grant.note in ("de_identified_only",), role


def test_unmask_is_separate_from_view():
    # CIA can view alerts (read-only) but cannot unmask PII — a separate, audited capability.
    assert rbac.is_allowed(Role.CHIEF_INTERNAL_AUDITOR, Capability.VIEW_ALERTS)
    assert not rbac.is_allowed(Role.CHIEF_INTERNAL_AUDITOR, Capability.UNMASK_PII)


def test_sod_deployer_cannot_label():
    ds = Principal(user_id="EMP-ds01", role=Role.DATA_SCIENCE_LEAD)
    with pytest.raises(sod.SoDError):
        sod.check_disposition(ds, alert_owner=None, subject_entity="EMP-7f3a")


def test_sod_no_self_review():
    rm = Principal(user_id="EMP-7f3a", role=Role.RELATIONSHIP_MANAGER)
    with pytest.raises(sod.SoDError):
        sod.check_disposition(rm, alert_owner=None, subject_entity="EMP-7f3a")


def test_sod_four_eyes():
    with pytest.raises(sod.SoDError):
        sod.check_four_eyes("EMP-co01", "EMP-co01")
    sod.check_four_eyes("EMP-co01", "EMP-tl01")  # ok, distinct


def test_sod_promotion_signoff_distinct():
    with pytest.raises(sod.SoDError):
        sod.check_promotion_signoff("EMP-ds01", "EMP-ds01")
    sod.check_promotion_signoff("EMP-ds01", "EMP-tl01")  # ok


def test_sod_investigator_cannot_tune_own_alert_rules():
    rm = Principal(
        user_id="EMP-rm01", role=Role.RELATIONSHIP_MANAGER, assigned_alerts={"alr_1"}
    )
    with pytest.raises(sod.SoDError):
        sod.check_rule_tuning(rm, generated_alerts={"alr_1"})
