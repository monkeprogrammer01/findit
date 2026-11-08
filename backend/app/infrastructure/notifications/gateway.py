"""Адаптеры к шлюзу уведомлений.

Email уходит по SMTP; в локальной разработке это MailHog (http://localhost:8025
показывает все письма). SMS пока заглушка за тем же интерфейсом: только пишет в лог.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.application.notifications import Message
from app.config import get_settings

log = logging.getLogger("findit.notifications")


class SmtpEmailSender:
    def __init__(self, host: str, port: int, sender: str) -> None:
        self._host, self._port, self._sender = host, port, sender

    def send(self, message: Message) -> None:
        if not message.to_email:
            return
        mail = EmailMessage()
        mail["From"] = self._sender
        mail["To"] = message.to_email
        mail["Subject"] = message.subject
        mail.set_content(message.body)
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.send_message(mail)


class SmsStub:
    def send(self, message: Message) -> None:
        if message.to_phone:
            log.info("SMS (stub) to %s: %s", message.to_phone, message.subject)


class EmailAndSmsNotifier:
    """Отправляет письмо, если есть email, иначе SMS."""

    def __init__(self, email: SmtpEmailSender, sms: SmsStub) -> None:
        self._email, self._sms = email, sms

    def send(self, message: Message) -> None:
        if message.to_email:
            self._email.send(message)
        else:
            self._sms.send(message)


def get_notifier() -> EmailAndSmsNotifier:
    """Зависимость FastAPI. В тестах подменяется на FakeNotifier."""
    settings = get_settings()
    return EmailAndSmsNotifier(
        SmtpEmailSender(settings.smtp_host, settings.smtp_port, settings.mail_from),
        SmsStub(),
    )
