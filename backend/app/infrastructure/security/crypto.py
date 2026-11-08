"""Шифрование AES-256-GCM для персональных данных (ограничение C-02)."""

import base64
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

_PREFIX = "v1:"  # версия формата: позволит сменить схему или ключ позже
_NONCE_SIZE = 12
# Только для локальной разработки и тестов. Вне local без настоящего ключа приложение не стартует.
_DEV_KEY = bytes(range(32))


class CryptoError(Exception):
    """Ключ задан неверно или данные не удалось расшифровать."""


@lru_cache
def _aesgcm() -> AESGCM:
    settings = get_settings()
    if settings.encryption_key:
        try:
            key = base64.b64decode(settings.encryption_key, validate=True)
        except ValueError as exc:
            raise CryptoError("FINDIT_ENCRYPTION_KEY must be valid base64") from exc
        if len(key) != 32:
            raise CryptoError("FINDIT_ENCRYPTION_KEY must decode to exactly 32 bytes")
    elif settings.environment == "local":
        key = _DEV_KEY
    else:
        raise CryptoError("FINDIT_ENCRYPTION_KEY is not set")
    return AESGCM(key)


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(_NONCE_SIZE)  # новый случайный nonce для каждого значения
    ciphertext = _aesgcm().encrypt(nonce, plaintext.encode("utf-8"), None)
    return _PREFIX + base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(value: str) -> str:
    if not value.startswith(_PREFIX):
        raise CryptoError("value is not encrypted")
    try:
        raw = base64.b64decode(value[len(_PREFIX) :])
        nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
        return _aesgcm().decrypt(nonce, ciphertext, None).decode("utf-8")
    except (ValueError, InvalidTag) as exc:
        raise CryptoError("decryption failed: wrong key or data was changed") from exc
