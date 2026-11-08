"""BE-9: автоматическое сопоставление отчётов о потере и найденных вещей.

Запускается сразу при создании найденной вещи (и при создании отчёта о потере),
в том же запросе: это один SQL-запрос по индексу категории, поэтому вся цепочка
вместе с фоновой отправкой письма укладывается в 60 секунд.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.matching import ItemFacts, is_match, match_score
from app.infrastructure.db.models import (
    FoundItem,
    FoundItemStatus,
    LostReport,
    LostReportStatus,
    MatchSuggestion,
)

# Отчёт уже с совпадением продолжает получать новые: первое совпадение могло быть не той вещью
ACTIVE_REPORTS = (LostReportStatus.open, LostReportStatus.matched)
AVAILABLE_ITEMS = (FoundItemStatus.stored, FoundItemStatus.eligible_for_disposal)


def _facts(obj: LostReport | FoundItem) -> ItemFacts:
    day = obj.lost_date if isinstance(obj, LostReport) else obj.found_date
    return ItemFacts(
        category=obj.category,
        location=obj.location,
        day=day,
        color=obj.color,
        serial_number=obj.serial_number,
        text=f"{obj.title} {obj.description or ''}",
    )


def _save(db: Session, report: LostReport, item: FoundItem, score: float) -> MatchSuggestion:
    existing = db.scalar(
        select(MatchSuggestion).where(
            MatchSuggestion.lost_report_id == report.id,
            MatchSuggestion.found_item_id == item.id,
        )
    )
    if existing is not None:
        existing.score = score
        return existing
    suggestion = MatchSuggestion(lost_report_id=report.id, found_item_id=item.id, score=score)
    db.add(suggestion)
    if report.status == LostReportStatus.open:
        report.status = LostReportStatus.matched
    return suggestion


def match_found_item(db: Session, item: FoundItem) -> list[tuple[LostReport, float]]:
    """Ищет открытые отчёты для новой найденной вещи. Возвращает новые пары."""
    candidates = db.scalars(
        select(LostReport).where(
            LostReport.category == item.category, LostReport.status.in_(ACTIVE_REPORTS)
        )
    )
    found = _facts(item)
    matches = []
    for report in candidates:
        score = match_score(_facts(report), found)
        if is_match(score):
            _save(db, report, item, score)
            matches.append((report, score))
    db.commit()
    return matches


def match_lost_report(db: Session, report: LostReport) -> list[tuple[FoundItem, float]]:
    """То же в обратную сторону: вещь могли найти раньше, чем студент подал отчёт."""
    candidates = db.scalars(
        select(FoundItem).where(
            FoundItem.category == report.category, FoundItem.status.in_(AVAILABLE_ITEMS)
        )
    )
    lost = _facts(report)
    matches = []
    for item in candidates:
        score = match_score(lost, _facts(item))
        if is_match(score):
            _save(db, report, item, score)
            matches.append((item, score))
    db.commit()
    return matches


def list_matches(db: Session, report_id: int) -> list[tuple[FoundItem, float]]:
    rows = db.execute(
        select(FoundItem, MatchSuggestion.score)
        .join(MatchSuggestion, MatchSuggestion.found_item_id == FoundItem.id)
        .where(MatchSuggestion.lost_report_id == report_id)
        .order_by(MatchSuggestion.score.desc(), FoundItem.id.desc())
    )
    return [(item, score) for item, score in rows]
