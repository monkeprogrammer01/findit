"""Ошибки прикладного слоя. В main.py они превращаются в HTTP-ответы."""


class NotFoundError(Exception):
    """Объект не найден (HTTP 404)."""


class BusinessRuleError(Exception):
    """Нарушено правило процесса, например заявка на уже выданную вещь (HTTP 409)."""


class StorageLimitError(Exception):
    """Хранилище фото заполнено, ограничение C-01 (HTTP 507)."""
