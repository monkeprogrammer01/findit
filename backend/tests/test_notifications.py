"""BE-11: шаблоны писем, SMTP-отправка и SMS-заглушка без настоящих серверов."""

import pytest
from fastapi import BackgroundTasks

from app.application.notifications import TEMPLATES, Message, build_message, notify
from app.infrastructure.db.models import User
from app.infrastructure.notifications import gateway


def user(email="a@stu.sdu.edu.kz", phone=None) -> User:
    return User(id=1, email=email, phone=phone)


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_every_template_renders(template):
    context = {
        "report_title": "Lost phone",
        "item_title": "Black iPhone",
        "score": 0.8,
        "storage_desk": "Desk A",
        "date": "2026-11-08",
    }
    message = build_message(user(), template, **context)
    assert message.to_email == "a@stu.sdu.edu.kz"
    assert "Black iPhone" in message.body
    assert "{" not in message.body


def test_user_without_contacts_gets_nothing():
    assert build_message(user(email=None), "claim_rejected", item_title="X") is None


def test_notify_runs_in_background_and_errors_do_not_escape():
    class Broken:
        def send(self, message):
            raise ConnectionError("SMTP is down")

    tasks = BackgroundTasks()
    notify(tasks, Broken(), user(), "claim_rejected", item_title="X")
    assert len(tasks.tasks) == 1
    tasks.tasks[0].func(*tasks.tasks[0].args)  # не бросает исключение


def test_smtp_sender_builds_email(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("mailhog", 1025)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def send_message(self, mail):
            sent.append(mail)

    monkeypatch.setattr(gateway.smtplib, "SMTP", FakeSMTP)
    sender = gateway.SmtpEmailSender("mailhog", 1025, "noreply@findit.local")
    sender.send(Message("a@stu.sdu.edu.kz", None, "Subject", "Body"))
    assert sent[0]["To"] == "a@stu.sdu.edu.kz"
    assert sent[0]["Subject"] == "Subject"


def test_phone_only_user_goes_to_sms_stub():
    calls = []

    class Email:
        def send(self, message):
            calls.append("email")

    class Sms:
        def send(self, message):
            calls.append("sms")

    notifier = gateway.EmailAndSmsNotifier(Email(), Sms())
    notifier.send(Message(None, "+77001234567", "S", "B"))
    notifier.send(Message("a@b.kz", None, "S", "B"))
    assert calls == ["sms", "email"]
