from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.audit import log_event
from app.application.auth import get_or_create_user
from app.infrastructure.auth.tokens import TokenError, verify_token
from app.infrastructure.db.models import User, UserRole
from app.infrastructure.db.session import get_db

# auto_error=False: иначе FastAPI вернёт 403, а нам нужен 401
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(credentials: Credentials, db: DbSession) -> User:
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        claims = verify_token(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized("Invalid or expired token") from exc
    return get_or_create_user(db, claims)


# Короткая запись для эндпоинтов: def handler(user: CurrentUser)
CurrentUser = Annotated[User, Depends(get_current_user)]


def forbid(request: Request, db: Session, user: User, reason: str) -> HTTPException:
    """Записывает отказ в audit_log и возвращает 403.

    Использовать так: raise forbid(request, db, user, "not the author").
    """
    log_event(
        db,
        action="forbidden",
        user_id=user.id,
        method=request.method,
        path=request.url.path,
        details=reason,
    )
    # В ответ не попадает ничего, кроме общего текста: причина только в журнале
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def require_role(*allowed: UserRole):
    allowed_names = ", ".join(role.value for role in allowed)

    def checker(request: Request, user: CurrentUser, db: DbSession) -> User:
        if user.role not in allowed:
            raise forbid(request, db, user, f"role={user.role.value}, required={allowed_names}")
        return user

    return checker


# Короткие записи для эндпоинтов: def handler(user: DeskAdmin)
DeskAdmin = Annotated[User, Depends(require_role(UserRole.desk_admin))]
SysAdmin = Annotated[User, Depends(require_role(UserRole.sys_admin))]
