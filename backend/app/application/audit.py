from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditLog


def log_event(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    method: str | None = None,
    path: str | None = None,
    details: str | None = None,
) -> None:
    """Добавляет запись в audit_log и сразу сохраняет её."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            method=method,
            path=path,
            details=details,
        )
    )
    db.commit()
