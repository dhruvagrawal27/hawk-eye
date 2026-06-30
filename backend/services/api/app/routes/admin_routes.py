"""Admin routes (BACKEND-22, blueprint Part 24.2 l.914).

GET/POST /admin/users — user/role management, Platform Admin only. Platform Admin sees no case
data (RBAC). Every admin change writes an audit event.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.auth.sod import constraints_for
from app.schemas.audit import CreateUserRequest, UserList, UserRecord
from app.schemas.common import Capability
from app.store.user_store import USER_STORE, User

router = APIRouter(tags=["admin"])


@router.get("/admin/users", response_model=UserList)
def list_users(
    principal: Principal = Depends(require_capability(Capability.ADMIN)),
) -> UserList:
    return UserList(items=[USER_STORE.to_record(u) for u in USER_STORE.list()])


@router.post("/admin/users", response_model=UserRecord, status_code=201)
def create_user(
    body: CreateUserRequest,
    principal: Principal = Depends(require_capability(Capability.ADMIN)),
) -> UserRecord:
    user = USER_STORE.add(
        User(user_id=body.user_id, display_name=body.display_name, role=body.role)
    )
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="admin.user_create",
        target=body.user_id,
        detail={"role": body.role.value},
    )
    return UserRecord(
        user_id=user.user_id,
        display_name=user.display_name,
        role=user.role,
        active=user.active,
        sod_constraints=constraints_for(user.role),
    )
