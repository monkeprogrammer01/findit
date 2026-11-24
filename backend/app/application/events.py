from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.application.audit import log_event


@dataclass(frozen=True)
class LostReportCreated:
    event_id: str
    report_id: int
    occurred_at: datetime


class EventBus:
    def __init__(self) -> None:
        self._handlers: list = []

    def subscribe(self, handler) -> None:
        self._handlers.append(handler)

    def publish(self, event: LostReportCreated, db: Session) -> None:
        for handler in self._handlers:
            handler(event, db)


event_bus = EventBus()
processed_event_ids: set[str] = set()


def handle_lost_report_created(event: LostReportCreated, db: Session) -> None:
    if event.event_id in processed_event_ids:
        return

    log_event(
        db,
        action="LOST_REPORT_CREATED",
        details=f"report_id={event.report_id}",
    )
    processed_event_ids.add(event.event_id)


event_bus.subscribe(handle_lost_report_created)