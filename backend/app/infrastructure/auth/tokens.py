from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.config import get_settings


class TokenError(Exception):
    """Токен недействителен: плохая подпись, истёк, чужой issuer и т.п."""


@dataclass
class TokenClaims:
    campus_id: str
    role: str | None
    email: str | None


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def _signing_key(token: str):
    settings = get_settings()
    if settings.oidc_jwks_url:
        return _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token).key
    if settings.environment == "local":
        from app.infrastructure.auth.fake_sso import public_key

        return public_key
    raise TokenError("SSO is not configured")


def verify_token(token: str) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    return TokenClaims(
        campus_id=payload["sub"], role=payload.get("role"), email=payload.get("email")
    )
