"""User directory (BACKEND-2/22).

# STUB: DATABASE (Postgres users table) + PLATFORM (Keycloak realm). Seeded synthetic users, one
per human role + the service account (plus legacy login aliases), used for local auth and
/admin/users. Passwords are a single synthetic dev secret — there is NO real credential here. In
keycloak mode the directory is read from Keycloak instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# NOTE: ``constraints_for`` is imported lazily inside ``to_record`` (not at module top) to break a
# circular import — ``app.auth`` eagerly imports ``oidc`` which imports this module, so importing
# ``app.auth.sod`` here at load time would deadlock when ``user_store`` is the entry point.
from app.schemas.audit import UserRecord
from app.schemas.common import Role

# Synthetic shared dev password for all seeded users (ON-PREM + SYNTHETIC ONLY).
DEV_PASSWORD = "hawk-eye"


@dataclass
class User:
    user_id: str
    display_name: str
    role: Role
    password: str = DEV_PASSWORD
    active: bool = True
    assigned_alerts: set[str] = field(default_factory=set)
    de_identified_only: bool = False
    scopes: list[str] = field(default_factory=list)


class UserStore:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._seed()

    def _seed(self) -> None:
        # Demo personas (mock login / seed users) — username → role, per docs/BANK_ROLES.md.
        # One user per human role + the service account; top-of-chart names mirror a PSB org chart.
        seed = [
            User("EMP-rm01", "Asha Nair (Relationship Manager)", Role.RELATIONSHIP_MANAGER),
            User("EMP-bm01", "Sunil Rao (Branch Manager)", Role.BRANCH_MANAGER),
            User("EMP-ch01", "Priya Deshmukh (Cluster Head / Zonal Manager)", Role.CLUSTER_HEAD),
            User("EMP-agm1", "Tara Iyer (AGM — Vigilance & Fraud Risk / MLRO)", Role.AGM_VIGILANCE),
            User("EMP-dgm1", "Carla D'Souza (DGM — Risk & Compliance)", Role.DGM_COMPLIANCE),
            User(
                "EMP-ds01",
                "Maya Krishnan (Head — Data Science / Model Risk)",
                Role.DATA_SCIENCE_LEAD,
                de_identified_only=True,
            ),
            User(
                "EMP-cgm1",
                "Vikram Rao (CGM — Chief Risk Officer)",
                Role.CGM_RISK,
                de_identified_only=True,
            ),
            User("EMP-cia1", "Anil Verma (Chief Internal Auditor)", Role.CHIEF_INTERNAL_AUDITOR),
            User(
                "EMP-ed01",
                "Lakshmi Menon (Executive Director)",
                Role.EXECUTIVE_DIRECTOR,
                de_identified_only=True,
            ),
            User(
                "EMP-md01",
                "Rajan Pillai (Managing Director & CEO)",
                Role.MANAGING_DIRECTOR,
                de_identified_only=True,
            ),
            User("EMP-it01", "Pat Sharma (IT / Platform Administrator)", Role.IT_ADMIN),
            User(
                "svc-ingest",
                "Ingest Service Account",
                Role.SERVICE_ACCOUNT,
                scopes=["events:write", "audit:write"],
            ),
        ]
        # Legacy demo logins kept as ALIASES (same role, capability profile preserved) so the
        # A→Z flow and existing tests stay green — docs/BANK_ROLES.md old→new mapping.
        aliases = [
            User("EMP-an01", "Asha Nair (Analyst → RM)", Role.RELATIONSHIP_MANAGER),
            User("EMP-sr01", "Sunil Rao (Senior Investigator → Branch Mgr)", Role.BRANCH_MANAGER),
            User("EMP-tl01", "Tara Iyer (Team Lead / MLRO → AGM Vigilance)", Role.AGM_VIGILANCE),
            User("EMP-co01", "Carla D'Souza (Compliance Officer → DGM)", Role.DGM_COMPLIANCE),
            User("EMP-co02", "Rohit Menon (Compliance Officer → DGM)", Role.DGM_COMPLIANCE),
            User("EMP-au01", "Anil Verma (Auditor → Chief Internal Auditor)", Role.CHIEF_INTERNAL_AUDITOR),
            User(
                "EMP-me01",
                "Maya Krishnan (Model Engineer → Data Science Lead)",
                Role.DATA_SCIENCE_LEAD,
                de_identified_only=True,
            ),
            User("EMP-pa01", "Pat Sharma (Platform Admin → IT Admin)", Role.IT_ADMIN),
        ]
        for u in (*seed, *aliases):
            self._users[u.user_id] = u

    def authenticate(self, user_id: str, password: str) -> User | None:
        user = self._users.get(user_id)
        if user and user.active and password == user.password:
            return user
        return None

    def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def add(self, user: User) -> User:
        self._users[user.user_id] = user
        return user

    def list(self) -> list[User]:
        return list(self._users.values())

    def assign_alert(self, user_id: str, alert_id: str) -> None:
        user = self._users.get(user_id)
        if user:
            user.assigned_alerts.add(alert_id)

    def to_record(self, user: User) -> UserRecord:
        from app.auth.sod import constraints_for  # lazy: see module-top note (circular import)

        return UserRecord(
            user_id=user.user_id,
            display_name=user.display_name,
            role=user.role,
            active=user.active,
            sod_constraints=constraints_for(user.role),
        )


USER_STORE = UserStore()
