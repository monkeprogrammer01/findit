"""BE-11: уведомления.

Сервис собирает письмо из шаблона, пока открыта сессия базы (email и телефон
расшифровываются при чтении пользователя), а саму отправку FastAPI выполняет
в фоне после ответа (BackgroundTasks), чтобы запрос не ждал SMTP-сервер.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from fastapi import BackgroundTasks

from app.infrastructure.db.models import User

log = logging.getLogger("findit.notifications")


@dataclass(frozen=True)
class Message:
    to_email: str | None
    to_phone: str | None
    subject: str
    body: str


class Notifier(Protocol):
    """Порт к шлюзу email/SMS. В тестах вместо него FakeNotifier."""

    def send(self, message: Message) -> None: ...


TEMPLATES = {
    "match_found": (
        "FindIt: possible match for your lost item",
        'Hello!\n\nA found item may match your report "{report_title}": '
        '"{item_title}" (match score {score:.0%}).\n'
        "Open FindIt to check it and submit a claim if it is yours.",
    ),
    "claim_approved": (
        "FindIt: your claim was approved",
        'Hello!\n\nYour claim for "{item_title}" was approved.\n'
        "Pick it up at {storage_desk}. Bring your student ID card.",
    ),
    "claim_rejected": (
        "FindIt: your claim was rejected",
        'Hello!\n\nYour claim for "{item_title}" was rejected. '
        "If you think this is a mistake, visit the lost and found desk.",
    ),
    "item_returned": (
        "FindIt: item handed over",
        'Hello!\n\n"{item_title}" was handed over to you on {date}. Thank you for using FindIt.',
    ),
}


def build_message(user: User, template: str, **context) -> Message | None:
    if not user.email and not user.phone:
        log.warning("user %s has no email or phone, %s not sent", user.id, template)
        return None
    subject, body = TEMPLATES[template]
    return Message(
        to_email=user.email,
        to_phone=user.phone,
        subject=subject,
        body=body.format(**context),
    )


def notify(
    background: BackgroundTasks, notifier: Notifier, user: User, template: str, **context
) -> None:
    """Поставить уведомление в очередь фоновых задач запроса."""
    message = build_message(user, template, **context)
    if message is not None:
        background.add_task(_send_safely, notifier, message)


def _send_safely(notifier: Notifier, message: Message) -> None:
    # ошибка почтового сервера не должна ломать уже выполненное действие
    try:
        notifier.send(message)
    except Exception:
        log.exception("failed to send notification %r", message.subject)
