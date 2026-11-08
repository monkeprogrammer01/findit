from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import FoundItem, Handover


def current_quarter(today: date | None = None) -> tuple[int, int]:
    today = today or datetime.now(UTC).date()
    return today.year, (today.month - 1) // 3 + 1


def quarter_bounds(year: int, quarter: int) -> tuple[datetime, datetime]:
    """Начало квартала (включительно) и начало следующего (не включительно)."""
    start_month = 3 * (quarter - 1) + 1
    start = datetime(year, start_month, 1, tzinfo=UTC)
    if quarter == 4:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, start_month + 3, 1, tzinfo=UTC)
    return start, end


def quarterly_report(db: Session, year: int, quarter: int) -> dict:
    start, end = quarter_bounds(year, quarter)

    def count(id_column, date_column) -> int:
        stmt = select(func.count(id_column)).where(date_column >= start, date_column < end)
        return db.scalar(stmt) or 0

    return {
        "year": year,
        "quarter": quarter,
        "period_start": start.date(),
        "period_end": (end - timedelta(days=1)).date(),
        "found": count(FoundItem.id, FoundItem.received_at),
        "returned": count(Handover.id, Handover.issued_at),
        "marked_for_disposal": count(FoundItem.id, FoundItem.disposal_flagged_at),
    }
