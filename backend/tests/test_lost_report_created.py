from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.application.events import LostReportCreated, event_bus, processed_event_ids
from app.infrastructure.db.models import AuditLog
from tests.test_lost_reports import create


def _audit_rows(session_factory):
    with session_factory() as session:
        return list(
            session.scalars(select(AuditLog).where(AuditLog.action == "LOST_REPORT_CREATED"))
        )


def test_creating_report_writes_one_audit_row(client, session_factory):
    processed_event_ids.clear()
    report = create(client)

    rows = _audit_rows(session_factory)
    assert len(rows) == 1
    assert rows[0].details == f"report_id={report['id']}"


def test_same_event_twice_writes_one_audit_row(session_factory):
    processed_event_ids.clear()
    event = LostReportCreated(
        event_id=str(uuid4()),
        report_id=1,
        occurred_at=datetime.now(UTC),
    )
    with session_factory() as session:
        event_bus.publish(event, session)
        event_bus.publish(event, session)

    rows = _audit_rows(session_factory)
    assert len(rows) == 1
