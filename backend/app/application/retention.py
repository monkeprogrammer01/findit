import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.application.app_settings import RETENTION_KEY, get_setting
from app.application.audit import log_event
from app.config import get_settings
from app.infrastructure.db.models import Claim, ClaimStatus, FoundItem, FoundItemStatus
from app.infrastructure.db.session import SessionLocal

logger = logging.getLogger(__name__)

# По вещам с такими заявками человек ещё пытается забрать вещь, их не трогаем
ACTIVE_CLAIMS = (ClaimStatus.pending, ClaimStatus.approved)


def get_retention_days(db: Session) -> int:
    """Срок хранения в днях: значение из базы (его меняет sys_admin), иначе из настроек."""
    value = get_setting(db, RETENTION_KEY)
    return int(value) if value is not None else get_settings().retention_days


def mark_overdue_items(db: Session, now: datetime | None = None) -> int:
    """Помечает вещи, которые не забрали за срок хранения. Возвращает их количество."""
    now = now or datetime.now(UTC)
    days = get_retention_days(db)
    cutoff = now - timedelta(days=days)
    with_active_claim = select(Claim.found_item_id).where(Claim.status.in_(ACTIVE_CLAIMS))
    result = db.execute(
        update(FoundItem)
        .where(
            FoundItem.status == FoundItemStatus.stored,
            FoundItem.received_at < cutoff,
            FoundItem.id.not_in(with_active_claim),
        )
        .values(status=FoundItemStatus.eligible_for_disposal, disposal_flagged_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    count = result.rowcount
    if count:
        log_event(db, action="retention_marked", details=f"{count} items older than {days} days")
    return count


def run_retention_job() -> int:
    """Запускается по расписанию: сама открывает сессию базы."""
    with SessionLocal() as db:
        count = mark_overdue_items(db)
    logger.info("Retention job: %s items marked eligible_for_disposal", count)
    return count
