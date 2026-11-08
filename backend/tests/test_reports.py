import csv
import io
from datetime import UTC, datetime

import pytest

from app.infrastructure.db.models import (
    CampusLocation,
    FoundItem,
    Handover,
    ItemCategory,
    VerificationMethod,
)
from tests.helpers import headers

SYS_ADMIN = headers("admin001", "sys_admin")


def at(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 12, 0, tzinfo=UTC)


def add_item(session, received: datetime, flagged: datetime | None = None) -> None:
    session.add(
        FoundItem(
            title="Item",
            category=ItemCategory.wallet,
            found_date=received.date(),
            location=CampusLocation.library,
            storage_desk="Desk A",
            storage_cell="Locker 1",
            received_at=received,
            disposal_flagged_at=flagged,
            created_by_id=1,
        )
    )


def add_handover(session, claim_id: int, issued: datetime) -> None:
    session.add(
        Handover(
            claim_id=claim_id,
            recipient_name="Aigerim",
            recipient_student_id="240107999",
            verification_method=VerificationMethod.student_id_in_person,
            issued_by_id=1,
            issued_at=issued,
        )
    )


@pytest.fixture
def data(session_factory):
    with session_factory() as session:
        add_item(session, at(10, 15), flagged=at(10, 20))  # Q4: найдена и помечена
        add_item(session, at(11, 1))  # Q4: найдена
        add_item(session, at(8, 1), flagged=at(8, 20))  # Q3: найдена и помечена
        add_handover(session, 1, at(11, 2))  # Q4: выдана
        add_handover(session, 2, at(8, 5))  # Q3: выдана
        session.commit()


def test_report_requires_login(client):
    assert client.get("/reports/quarterly").status_code == 401


@pytest.mark.parametrize(("who", "role"), [("student001", "student"), ("desk001", "desk_admin")])
def test_only_sys_admin_can_read_report(client, who, role):
    response = client.get("/reports/quarterly", headers=headers(who, role))
    assert response.status_code == 403


def test_q4_counts(client, data):
    response = client.get(
        "/reports/quarterly", params={"year": 2026, "quarter": 4}, headers=SYS_ADMIN
    )
    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "quarter": 4,
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "found": 2,
        "returned": 1,
        "marked_for_disposal": 1,
    }


def test_q3_counts(client, data):
    response = client.get(
        "/reports/quarterly", params={"year": 2026, "quarter": 3}, headers=SYS_ADMIN
    )
    body = response.json()
    assert (body["found"], body["returned"], body["marked_for_disposal"]) == (1, 1, 1)
    assert body["period_start"] == "2026-07-01"
    assert body["period_end"] == "2026-09-30"


def test_empty_quarter_returns_zeros(client, data):
    response = client.get(
        "/reports/quarterly", params={"year": 2025, "quarter": 1}, headers=SYS_ADMIN
    )
    body = response.json()
    assert (body["found"], body["returned"], body["marked_for_disposal"]) == (0, 0, 0)


def test_csv_export(client, data):
    response = client.get(
        "/reports/quarterly",
        params={"year": 2026, "quarter": 4, "format": "csv"},
        headers=SYS_ADMIN,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="quarterly-2026-Q4.csv"' in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows == [
        {
            "year": "2026",
            "quarter": "4",
            "period_start": "2026-10-01",
            "period_end": "2026-12-31",
            "found": "2",
            "returned": "1",
            "marked_for_disposal": "1",
        }
    ]


def test_default_is_current_quarter(client):
    body = client.get("/reports/quarterly", headers=SYS_ADMIN).json()
    assert body["year"] == datetime.now(UTC).year
    assert body["quarter"] in (1, 2, 3, 4)


@pytest.mark.parametrize(
    "params",
    [{"quarter": 5, "year": 2026}, {"quarter": 0, "year": 2026}, {"format": "xml"}, {"year": 2026}],
)
def test_bad_parameters_are_rejected(client, params):
    response = client.get("/reports/quarterly", params=params, headers=SYS_ADMIN)
    assert response.status_code == 422
