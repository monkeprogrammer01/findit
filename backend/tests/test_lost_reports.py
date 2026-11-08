from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.infrastructure.auth.fake_sso import issue_token
from app.infrastructure.db.models import AuditLog


def headers(campus_id: str = "student001", role: str = "student") -> dict:
    return {"Authorization": f"Bearer {issue_token(campus_id, role)}"}


def payload(**overrides) -> dict:
    data = {
        "title": "Black laptop bag",
        "category": "bag",
        "lost_date": (date.today() - timedelta(days=1)).isoformat(),
        "location": "library",
        "color": "black",
        "serial_number": None,
        "description": "Has a sticker",
    }
    data.update(overrides)
    return data


def create(client, who: str = "student001", **overrides) -> dict:
    response = client.post("/lost-reports", json=payload(**overrides), headers=headers(who))
    assert response.status_code == 201, response.text
    return response.json()


FUTURE = (date.today() + timedelta(days=1)).isoformat()
OTHERS = [("student002", "student"), ("desk001", "desk_admin"), ("admin001", "sys_admin")]


def test_create_requires_login(client):
    assert client.post("/lost-reports", json=payload()).status_code == 401


def test_create_report(client):
    report = create(client)
    assert report["status"] == "open"
    assert report["title"] == "Black laptop bag"
    assert report["category"] == "bag"


@pytest.mark.parametrize(
    "bad",
    [
        {"category": "spaceship"},
        {"location": "moon"},
        {"title": "   "},
        {"title": ""},
        {"lost_date": FUTURE},
        {"lost_date": "not-a-date"},
    ],
)
def test_create_validation(client, bad):
    response = client.post("/lost-reports", json=payload(**bad), headers=headers())
    assert response.status_code == 422


def test_create_without_title_is_rejected(client):
    data = payload()
    del data["title"]
    assert client.post("/lost-reports", json=data, headers=headers()).status_code == 422


def test_me_lists_only_own_reports(client):
    mine = create(client, "student001", title="Mine")
    create(client, "student002", title="Theirs")
    response = client.get("/lost-reports/me", headers=headers("student001"))
    assert [r["id"] for r in response.json()] == [mine["id"]]


def test_me_pagination_newest_first(client):
    ids = [create(client, title=f"Item {i}")["id"] for i in range(3)]
    page = client.get("/lost-reports/me", params={"limit": 2}, headers=headers()).json()
    assert [r["id"] for r in page] == [ids[2], ids[1]]
    rest = client.get("/lost-reports/me", params={"limit": 2, "offset": 2}, headers=headers())
    assert [r["id"] for r in rest.json()] == [ids[0]]


def test_me_rejects_bad_limit(client):
    response = client.get("/lost-reports/me", params={"limit": 0}, headers=headers())
    assert response.status_code == 422


def test_author_can_read_report(client):
    report = create(client)
    response = client.get(f"/lost-reports/{report['id']}", headers=headers())
    assert response.status_code == 200
    assert response.json()["id"] == report["id"]


def test_other_student_cannot_read_and_denial_is_audited(client, session_factory):
    report = create(client)
    url = f"/lost-reports/{report['id']}"
    response = client.get(url, headers=headers("student002"))
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
    with session_factory() as session:
        rows = list(session.scalars(select(AuditLog)))
    assert len(rows) == 1
    assert rows[0].action == "forbidden"
    assert rows[0].path == url


def test_staff_can_read_any_report(client):
    report = create(client)
    url = f"/lost-reports/{report['id']}"
    assert client.get(url, headers=headers("desk001", "desk_admin")).status_code == 200
    assert client.get(url, headers=headers("admin001", "sys_admin")).status_code == 200


def test_unknown_report_returns_404(client):
    assert client.get("/lost-reports/999", headers=headers()).status_code == 404


def test_author_can_update_only_sent_fields(client):
    report = create(client)
    response = client.patch(
        f"/lost-reports/{report['id']}",
        json={"title": "New title", "status": "closed"},
        headers=headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "New title"
    assert body["status"] == "closed"
    assert body["category"] == "bag"  # не присылали, значит не изменилось


def test_others_cannot_update(client):
    report = create(client)
    url = f"/lost-reports/{report['id']}"
    for who, role in OTHERS:
        response = client.patch(url, json={"title": "Hacked"}, headers=headers(who, role))
        assert response.status_code == 403
    assert client.get(url, headers=headers()).json()["title"] == "Black laptop bag"


@pytest.mark.parametrize(
    "bad",
    [
        {"title": None},
        {"category": None},
        {"status": "matched"},
        {"lost_date": FUTURE},
        {"category": "spaceship"},
    ],
)
def test_update_validation(client, bad):
    report = create(client)
    response = client.patch(f"/lost-reports/{report['id']}", json=bad, headers=headers())
    assert response.status_code == 422


def test_author_can_delete(client):
    report = create(client)
    url = f"/lost-reports/{report['id']}"
    assert client.delete(url, headers=headers()).status_code == 204
    assert client.get(url, headers=headers()).status_code == 404


def test_others_cannot_delete(client):
    report = create(client)
    url = f"/lost-reports/{report['id']}"
    for who, role in OTHERS:
        assert client.delete(url, headers=headers(who, role)).status_code == 403
    assert client.get(url, headers=headers()).status_code == 200
