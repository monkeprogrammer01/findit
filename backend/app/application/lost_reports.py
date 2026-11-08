from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import LostReport


def create_report(db: Session, author_id: int, data: dict) -> LostReport:
    report = LostReport(author_id=author_id, **data)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports_by_author(
    db: Session, author_id: int, limit: int, offset: int
) -> list[LostReport]:
    stmt = (
        select(LostReport)
        .where(LostReport.author_id == author_id)
        .order_by(LostReport.created_at.desc(), LostReport.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def get_report(db: Session, report_id: int) -> LostReport | None:
    return db.get(LostReport, report_id)


def update_report(db: Session, report: LostReport, changes: dict) -> LostReport:
    for field, value in changes.items():
        setattr(report, field, value)
    db.commit()
    db.refresh(report)
    return report


def delete_report(db: Session, report: LostReport) -> None:
    db.delete(report)
    db.commit()
