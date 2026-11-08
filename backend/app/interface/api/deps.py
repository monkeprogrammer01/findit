from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.auth import get_or_create_user
from app.infrastructure.auth.tokens import TokenError, verify_token
from app.infrastructure.db.models import User
from app.infrastructure.db.session import get_db

# auto_error=False: иначе FastAPI вернёт 403, а нам нужен 401
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        claims = verify_token(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized("Invalid or expired token") from exc
    return get_or_create_user(db, claims)
