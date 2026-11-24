from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.events import ItemReturned
from app.infrastructure.db.models import ItemCategory, ProcessedEvent, ReturnStatistic

CONSUMER_NAME = "return_statistics"


class ReturnStatisticsConsumer:
    def __init__(self, db: Session) -> None:
        self._db = db

    def handle(self, event: ItemReturned) -> None:
        if self._already_processed(event.event_id):
            return

        stat = self._db.get(ReturnStatistic, ItemCategory(event.category))
        if stat is None:
            stat = ReturnStatistic(category=ItemCategory(event.category), returned_count=0)
            self._db.add(stat)
        stat.returned_count += 1
        stat.last_returned_at = event.occurred_at
        self._db.add(ProcessedEvent(event_id=event.event_id, consumer=CONSUMER_NAME))
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()

    def _already_processed(self, event_id: str) -> bool:
        found = self._db.scalar(
            select(ProcessedEvent.event_id).where(
                ProcessedEvent.event_id == event_id,
                ProcessedEvent.consumer == CONSUMER_NAME,
            )
        )
        return found is not None


def returned_count(db: Session, category: ItemCategory) -> int:
    stat = db.get(ReturnStatistic, category)
    return stat.returned_count if stat else 0
