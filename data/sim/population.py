"""Population generator: N employees mirroring an org shape (DATA-8).

Blueprint Part 21.1 #1 (l.795). Generates employees with role / department / branch /
tenure_days / manager_id / peer_group / privileged_flag, configurable up to ~50k staff
with a few hundred privileged. Deterministic from SimConfig.seed.

Status: REAL. Synthetic-only — every id comes from make_id('employee', ...) so no real PII
is ever produced (golden rule 2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from data.config import SimConfig, make_id

# Roles mirroring a bank org (blueprint 21.1 / Part 12 typologies need these actors).
ROLES: tuple[str, ...] = (
    "teller",
    "ops_maker",
    "ops_checker",
    "dba",
    "sysadmin",
    "loan_officer",
    "appraiser",
    "trader",
    "aml_analyst",
    "vendor_admin",
)

# Approximate role mix (weights need not sum to 1; rng.choice normalizes).
ROLE_WEIGHTS: dict[str, float] = {
    "teller": 0.34,
    "ops_maker": 0.14,
    "ops_checker": 0.12,
    "dba": 0.03,
    "sysadmin": 0.03,
    "loan_officer": 0.10,
    "appraiser": 0.05,
    "trader": 0.05,
    "aml_analyst": 0.06,
    "vendor_admin": 0.08,
}

# Which roles are inherently privileged (DBAs/sysadmins/vendor_admins handle entitlements).
PRIVILEGED_ROLES: frozenset[str] = frozenset({"dba", "sysadmin", "vendor_admin"})

ROLE_DEPT: dict[str, str] = {
    "teller": "retail_branch",
    "ops_maker": "trade_finance",
    "ops_checker": "trade_finance",
    "dba": "it_infra",
    "sysadmin": "it_infra",
    "loan_officer": "credit",
    "appraiser": "credit",
    "trader": "treasury",
    "aml_analyst": "compliance",
    "vendor_admin": "procurement",
}


@dataclass
class Employee:
    employee_id: str
    role: str
    dept: str
    branch: str
    tenure_days: int
    manager_id: Optional[str]
    peer_group: str
    privileged_flag: bool
    # synthetic personal attributes used by slow-lane typologies (fake-vendor address match,
    # ghost-employee duplicated bank details). Synthetic-only ids, never real PII.
    address_id: str = ""
    bank_account: str = ""

    def to_actor_kwargs(self) -> dict:
        return {
            "employee_id": self.employee_id,
            "role": self.role,
            "dept": self.dept,
            "branch": self.branch,
            "tenure_days": self.tenure_days,
            "manager_id": self.manager_id,
            "peer_group": self.peer_group,
            "privileged_flag": self.privileged_flag,
        }


def generate_population(cfg: SimConfig) -> list[Employee]:
    """Generate cfg.n_employees deterministic employees.

    A few hundred privileged out of ~50k at production scale is achieved via
    PRIVILEGED_ROLES plus cfg.privileged_fraction promotions among the rest.
    """
    rng = np.random.default_rng(cfg.seed)
    n = cfg.n_employees

    roles = list(ROLE_WEIGHTS.keys())
    weights = np.array([ROLE_WEIGHTS[r] for r in roles], dtype=float)
    weights = weights / weights.sum()

    n_branches = max(1, n // 40)
    branches = [f"BR-{200 + i}" for i in range(n_branches)]

    employees: list[Employee] = []
    # First pass: assign role/dept/branch/tenure; managers wired in a second pass.
    role_idx = rng.choice(len(roles), size=n, p=weights)
    branch_idx = rng.integers(0, n_branches, size=n)
    tenures = rng.integers(30, 365 * 20, size=n)
    priv_promote = rng.random(size=n) < cfg.privileged_fraction

    for i in range(n):
        role = roles[int(role_idx[i])]
        dept = ROLE_DEPT[role]
        branch = branches[int(branch_idx[i])]
        emp_id = make_id("employee", cfg.seed, i, role)
        peer_group = f"PG-{role}-{branch}"
        privileged = role in PRIVILEGED_ROLES or bool(priv_promote[i])
        employees.append(
            Employee(
                employee_id=emp_id,
                role=role,
                dept=dept,
                branch=branch,
                tenure_days=int(tenures[i]),
                manager_id=None,
                peer_group=peer_group,
                privileged_flag=privileged,
                address_id=make_id("employee", "addr", cfg.seed, i),
                bank_account=make_id("account", "payroll", cfg.seed, i),
            )
        )

    # Second pass: wire each employee to a manager in the same branch (the most senior peer).
    by_branch: dict[str, list[int]] = {}
    for i, e in enumerate(employees):
        by_branch.setdefault(e.branch, []).append(i)
    for _branch, idxs in by_branch.items():
        # most senior (longest tenure) in branch is the manager anchor
        anchor = max(idxs, key=lambda j: employees[j].tenure_days)
        for j in idxs:
            if j != anchor:
                employees[j].manager_id = employees[anchor].employee_id
    return employees


def by_role(population: list[Employee], role: str) -> list[Employee]:
    return [e for e in population if e.role == role]


def demo() -> list[Employee]:
    """Tiny helper for tests."""
    return generate_population(SimConfig(n_employees=40, days=2, seed=7))
