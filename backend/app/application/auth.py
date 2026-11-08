import hashlib
import hmac

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.infrastructure.auth.tokens import TokenClaims
from app.infrastructure.db.models import User, UserRole


def hash_campus_id(campus_id: str) -> str:
    """Хэш для поиска пользователя: после шифрования (BE-5) по campus_id искать нельзя."""
    key = get_settings().campus_id_hash_key.encode()
    return hmac.new(key, campus_id.encode(), hashlib.sha256).hexdigest()


def get_or_create_user(db: Session, claims: TokenClaims) -> User:
    campus_hash = hash_campus_id(claims.campus_id)
    user = db.scalar(select(User).where(User.campus_id_hash == campus_hash))
    if user is None:
        valid_roles = {r.value for r in UserRole}
        role = UserRole(claims.role) if claims.role in valid_roles else UserRole.student
        user = User(
            campus_id=claims.campus_id,
            campus_id_hash=campus_hash,
            role=role,
            email=claims.email,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
