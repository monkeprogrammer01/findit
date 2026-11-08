from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.application.retention import mark_overdue_items
from app.config import get_settings
from app.infrastructure.db.models import (
    AuditLog,
    CampusLocation,
    Claim,
    ClaimStatus,
    FoundItem,
    FoundItemStatus,
    ItemCategory,
)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def add_item(session, days_old: int, status=FoundItemStatus.stored) -> int:
    item = FoundItem(
        title="Item",
        category=ItemCategory.wallet,
        found_date=NOW.date(),
        location=CampusLocation.library,
        storage_desk="Desk A",
        storage_cell="Locker 1",
        status=status,
        received_at=NOW - timedelta(days=days_old),
        created_by_id=1,
    )
    session.add(item)
    session.commit()
    return item.id


def add_claim(session, item_id: int, status: ClaimStatus) -> None:
    session.add(Claim(found_item_id=item_id, claimant_id=1, answers="{}", status=status))
    session.commit()


def status_of(session, item_id: int) -> FoundItemStatus:
    session.expire_all()
    return session.get(FoundItem, item_id).status


def test_marks_only_stored_items_older_than_retention(session_factory):
    with session_factory() as session:
        old = add_item(session, 91)
        fresh = add_item(session, 89)
        returned = add_item(session, 200, FoundItemStatus.returned)
        claimed = add_item(session, 200, FoundItemStatus.claimed)

        assert mark_overdue_items(session, now=NOW) == 1

        assert status_of(session, old) == FoundItemStatus.eligible_for_disposal
        assert status_of(session, fresh) == FoundItemStatus.stored
        assert status_of(session, returned) == FoundItemStatus.returned
        assert status_of(session, claimed) == FoundItemStatus.claimed


def test_item_exactly_at_limit_is_not_marked(session_factory):
    with session_factory() as session:
        item_id = add_item(session, 90)
        assert mark_overdue_items(session, now=NOW) == 0
        assert status_of(session, item_id) == FoundItemStatus.stored


def test_items_with_active_claims_are_not_marked(session_factory):
    with session_factory() as session:
        pending = add_item(session, 100)
        add_claim(session, pending, ClaimStatus.pending)
        approved = add_item(session, 100)
        add_claim(session, approved, ClaimStatus.approved)
        rejected = add_item(session, 100)
        add_claim(session, rejected, ClaimStatus.rejected)

        assert mark_overdue_items(session, now=NOW) == 1

        assert status_of(session, pending) == FoundItemStatus.stored
        assert status_of(session, approved) == FoundItemStatus.stored
        assert status_of(session, rejected) == FoundItemStatus.eligible_for_disposal


def test_flag_time_is_recorded(session_factory):
    with session_factory() as session:
        item_id = add_item(session, 100)
        mark_overdue_items(session, now=NOW)
        session.expire_all()
        assert session.get(FoundItem, item_id).disposal_flagged_at is not None


def test_second_run_marks_nothing(session_factory):
    with session_factory() as session:
        add_item(session, 100)
        assert mark_overdue_items(session, now=NOW) == 1
        assert mark_overdue_items(session, now=NOW) == 0


def test_retention_period_comes_from_settings(session_factory, monkeypatch):
    monkeypatch.setattr(get_settings(), "retention_days", 30)
    with session_factory() as session:
        add_item(session, 40)
        assert mark_overdue_items(session, now=NOW) == 1


def test_marking_is_written_to_audit_log(session_factory):
    with session_factory() as session:
        add_item(session, 100)
        mark_overdue_items(session, now=NOW)
        rows = list(session.scalars(select(AuditLog)))
    assert len(rows) == 1
    assert rows[0].action == "retention_marked"
    assert "1 items" in rows[0].details


def test_nothing_to_mark_writes_no_audit_entry(session_factory):
    with session_factory() as session:
        add_item(session, 10)
        mark_overdue_items(session, now=NOW)
        assert list(session.scalars(select(AuditLog))) == []
