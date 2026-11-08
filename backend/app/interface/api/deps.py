from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.auth import get_or_create_user
from app.infrastructure.auth.tokens import TokenError, verify_token
from app.infrastructure.db.models import User
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
