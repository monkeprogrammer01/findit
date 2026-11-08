"""Типы колонок SQLAlchemy: шифруют значение при записи и расшифровывают при чтении."""

from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator

from app.infrastructure.security.crypto import decrypt, encrypt


class _EncryptedMixin:
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(value)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)


class EncryptedString(_EncryptedMixin, TypeDecorator):
    """Короткие поля (email, телефон, campus_id). В базе это обычный VARCHAR."""

    impl = String


class EncryptedText(_EncryptedMixin, TypeDecorator):
    """Длинные поля (ответы на вопросы). В базе это обычный TEXT."""

    impl = Text
