from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.auth import hash_campus_id
from app.infrastructure.db.models import AuditLog, User, UserRole


def list_users(
    db: Session, role: UserRole | None, campus_id: str | None, limit: int, offset: int
) -> list[User]:
    stmt = select(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if campus_id is not None:
        # campus_id зашифрован, поэтому ищем по хэшу
        stmt = stmt.where(User.campus_id_hash == hash_campus_id(campus_id))
    return list(db.scalars(stmt.order_by(User.id).limit(limit).offset(offset)))


def change_role(db: Session, user: User, new_role: UserRole) -> User:
    user.role = new_role
    db.commit()
    db.refresh(user)
    return user


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def list_audit_entries(
    db: Session,
    *,
    user_id: int | None,
    action: str | None,
    path: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if path:
        stmt = stmt.where(AuditLog.path.startswith(path, autoescape=True))
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= _day_start(date_from))
    if date_to is not None:  # включительно: до начала следующего дня
        stmt = stmt.where(AuditLog.created_at < _day_start(date_to + timedelta(days=1)))
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    return list(db.scalars(stmt.limit(limit).offset(offset)))
