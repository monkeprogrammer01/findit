"""Фейковый SSO для локальной разработки: выдаёт подписанные RS256-токены."""

from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key = _private_key.public_key()
_private_pem = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

# по одному тестовому пользователю на каждую роль
TEST_USERS = {
    "student": "student001",
    "desk_admin": "desk001",
    "sys_admin": "admin001",
}


def issue_token(
    campus_id: str, role: str | None, email: str | None = None, expires_in: int = 3600
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "sub": campus_id,
        "role": role,
        "email": email,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(claims, _private_pem, algorithm="RS256")
