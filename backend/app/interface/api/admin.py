from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.application import admin as service
from app.application.app_settings import RETENTION_KEY, set_setting
from app.application.audit import log_event
from app.application.retention import get_retention_days
from app.infrastructure.db.models import User, UserRole
from app.interface.api.deps import DbSession, SysAdmin

router = APIRouter(prefix="/admin", tags=["admin"])

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: str
    role: UserRole
    email: str | None
    phone: str | None
    created_at: datetime


class RoleChange(BaseModel):
    role: UserRole


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    method: str | None
    path: str | None
    details: str | None
    created_at: datetime


class RetentionSetting(BaseModel):
    days: int = Field(ge=1, le=3650)


@router.get("/users", response_model=list[UserOut])
def list_users(
    admin: SysAdmin,
    db: DbSession,
    role: UserRole | None = None,
    campus_id: str | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return service.list_users(db, role, campus_id, limit, offset)


@router.patch("/users/{user_id}/role", response_model=UserOut)
def change_user_role(
    user_id: int, data: RoleChange, request: Request, admin: SysAdmin, db: DbSession
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot change your own role")
    old_role = target.role
    if old_role == data.role:
        return target
    target = service.change_role(db, target, data.role)
    log_event(
        db,
        action="role_changed",
        user_id=admin.id,
        method=request.method,
        path=request.url.path,
        details=f"user_id={target.id} {old_role.value} -> {target.role.value}",
    )
    return target


@router.get("/audit-log", response_model=list[AuditEntryOut])
def read_audit_log(
    admin: SysAdmin,
    db: DbSession,
    user_id: int | None = None,
    action: str | None = None,
    path: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return service.list_audit_entries(
        db,
        user_id=user_id,
        action=action,
        path=path,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/settings/retention", response_model=RetentionSetting)
def read_retention(admin: SysAdmin, db: DbSession):
    return RetentionSetting(days=get_retention_days(db))


@router.put("/settings/retention", response_model=RetentionSetting)
def update_retention(data: RetentionSetting, request: Request, admin: SysAdmin, db: DbSession):
    old_days = get_retention_days(db)
    set_setting(db, RETENTION_KEY, str(data.days), admin.id)
    log_event(
        db,
        action="retention_changed",
        user_id=admin.id,
        method=request.method,
        path=request.url.path,
        details=f"retention_days {old_days} -> {data.days}",
    )
    return data
