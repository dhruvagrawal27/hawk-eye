"""User directory (BACKEND-2/22).

# STUB: DATABASE (Postgres users table) + PLATFORM (Keycloak realm). Seeded synthetic users, one
per role, used for local auth and /admin/users. Passwords are a single synthetic dev secret —
there is NO real credential here. In keycloak mode the directory is read from Keycloak instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.auth.sod import constraints_for
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
        seed = [
            User("EMP-an01", "Asha Nair (Analyst)", Role.ANALYST, assigned_alerts={"alr_demo01"}),
            User("EMP-sr01", "Sunil Rao (Senior Investigator)", Role.SENIOR_INVESTIGATOR),
            User("EMP-tl01", "Tara Iyer (Team Lead / MLRO)", Role.TEAM_LEAD),
            User("EMP-co01", "Carla D'Souza (Compliance Officer)", Role.COMPLIANCE_OFFICER),
            User("EMP-co02", "Rohit Menon (Compliance Officer)", Role.COMPLIANCE_OFFICER),
            User("EMP-au01", "Anil Verma (Auditor)", Role.AUDITOR),
            User(
                "EMP-me01",
                "Maya Krishnan (Model Engineer)",
                Role.MODEL_ENGINEER,
                de_identified_only=True,
            ),
            User("EMP-pa01", "Pat Sharma (Platform Admin)", Role.PLATFORM_ADMIN),
            User(
                "svc-ingest",
                "Ingest Service Account",
                Role.SERVICE_ACCOUNT,
                scopes=["events:write", "audit:write"],
            ),
        ]
        for u in seed:
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
        return UserRecord(
            user_id=user.user_id,
            display_name=user.display_name,
            role=user.role,
            active=user.active,
            sod_constraints=constraints_for(user.role),
        )


USER_STORE = UserStore()
