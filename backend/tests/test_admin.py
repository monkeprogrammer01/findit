from datetime import UTC, datetime, timedelta

import pytest

from app.application.retention import mark_overdue_items
from app.config import get_settings
from app.infrastructure.db.models import CampusLocation, FoundItem, ItemCategory
from tests.helpers import headers

SYS = headers("admin001", "sys_admin")
DESK = headers("desk001", "desk_admin")
STUDENT = headers("student001")

ENDPOINTS = [
    ("GET", "/admin/users", None),
    ("PATCH", "/admin/users/1/role", {"role": "desk_admin"}),
    ("GET", "/admin/audit-log", None),
    ("GET", "/admin/settings/retention", None),
    ("PUT", "/admin/settings/retention", {"days": 60}),
]


def login(client, campus_id: str, role: str = "student") -> int:
    """Первый запрос создаёт пользователя; возвращает его id."""
    response = client.get("/me", headers=headers(campus_id, role))
    assert response.status_code == 200
    return response.json()["id"]


@pytest.mark.parametrize(("method", "url", "body"), ENDPOINTS)
def test_requires_login(client, method, url, body):
    assert client.request(method, url, json=body).status_code == 401


@pytest.mark.parametrize(("method", "url", "body"), ENDPOINTS)
@pytest.mark.parametrize("who", [STUDENT, DESK])
def test_only_sys_admin_has_access(client, method, url, body, who):
    assert client.request(method, url, json=body, headers=who).status_code == 403


def test_list_users_returns_decrypted_data(client):
    login(client, "student001")
    login(client, "desk001", "desk_admin")
    response = client.get("/admin/users", headers=SYS)
    assert response.status_code == 200
    users = {u["campus_id"]: u for u in response.json()}
    assert set(users) == {"student001", "desk001", "admin001"}
    assert users["student001"]["email"] == "student001@stu.sdu.edu.kz"
    assert users["desk001"]["role"] == "desk_admin"


def test_filter_users_by_role(client):
    login(client, "student001")
    login(client, "desk001", "desk_admin")
    response = client.get("/admin/users", params={"role": "desk_admin"}, headers=SYS)
    assert [u["campus_id"] for u in response.json()] == ["desk001"]


def test_filter_users_by_exact_campus_id(client):
    login(client, "student001")
    found = client.get("/admin/users", params={"campus_id": "student001"}, headers=SYS)
    assert [u["campus_id"] for u in found.json()] == ["student001"]
    missing = client.get("/admin/users", params={"campus_id": "nobody"}, headers=SYS)
    assert missing.json() == []


def test_users_pagination(client):
    for i in range(3):
        login(client, f"student10{i}")
    first = client.get("/admin/users", params={"limit": 2}, headers=SYS).json()
    rest = client.get("/admin/users", params={"limit": 2, "offset": 2}, headers=SYS).json()
    assert len(first) == 2
    assert len(rest) == 2  # всего 4: три студента и сам администратор
    assert not {u["id"] for u in first} & {u["id"] for u in rest}


def test_changed_role_takes_effect_immediately(client):
    student_id = login(client, "student001")
    response = client.patch(
        f"/admin/users/{student_id}/role", json={"role": "desk_admin"}, headers=SYS
    )
    assert response.status_code == 200
    assert response.json()["role"] == "desk_admin"
    # токен студента по-прежнему говорит "student", но роль берётся из базы
    assert client.get("/me", headers=STUDENT).json()["role"] == "desk_admin"


def test_role_change_is_audited(client):
    student_id = login(client, "student001")
    admin_id = login(client, "admin001", "sys_admin")
    client.patch(f"/admin/users/{student_id}/role", json={"role": "desk_admin"}, headers=SYS)
    entries = client.get("/admin/audit-log", params={"action": "role_changed"}, headers=SYS)
    assert len(entries.json()) == 1
    entry = entries.json()[0]
    assert entry["user_id"] == admin_id
    assert f"user_id={student_id}" in entry["details"]
    assert "student -> desk_admin" in entry["details"]


def test_admin_cannot_change_own_role(client):
    admin_id = login(client, "admin001", "sys_admin")
    response = client.patch(f"/admin/users/{admin_id}/role", json={"role": "student"}, headers=SYS)
    assert response.status_code == 400
    assert client.get("/me", headers=SYS).json()["role"] == "sys_admin"


def test_unknown_user_and_bad_role(client):
    student_id = login(client, "student001")
    missing = client.patch("/admin/users/999/role", json={"role": "desk_admin"}, headers=SYS)
    assert missing.status_code == 404
    bad = client.patch(f"/admin/users/{student_id}/role", json={"role": "king"}, headers=SYS)
    assert bad.status_code == 422


def test_audit_log_filters(client):
    student_id = login(client, "student001")
    for url in ("/admin/users", "/admin/audit-log"):  # студенту отказ, запись в журнал
        assert client.get(url, headers=STUDENT).status_code == 403
    today = datetime.now(UTC).date()

    def entries(**params):
        response = client.get("/admin/audit-log", params=params, headers=SYS)
        assert response.status_code == 200
        return response.json()

    # сначала самые новые
    assert [e["path"] for e in entries()] == ["/admin/audit-log", "/admin/users"]
    assert len(entries(user_id=student_id)) == 2
    assert entries(user_id=student_id + 100) == []
    assert len(entries(action="forbidden")) == 2
    assert entries(action="role_changed") == []
    assert [e["path"] for e in entries(path="/admin/users")] == ["/admin/users"]
    assert len(entries(path="/admin")) == 2
    assert len(entries(date_from=today.isoformat(), date_to=today.isoformat())) == 2
    assert entries(date_from=(today + timedelta(days=1)).isoformat()) == []
    assert entries(date_to=(today - timedelta(days=1)).isoformat()) == []
    assert len(entries(limit=1)) == 1


def test_retention_setting_default_and_update(client):
    url = "/admin/settings/retention"
    assert client.get(url, headers=SYS).json() == {"days": get_settings().retention_days}

    response = client.put(url, json={"days": 30}, headers=SYS)
    assert response.status_code == 200
    assert response.json() == {"days": 30}
    assert client.get(url, headers=SYS).json() == {"days": 30}

    client.put(url, json={"days": 45}, headers=SYS)  # второй раз обновляет значение
    assert client.get(url, headers=SYS).json() == {"days": 45}


@pytest.mark.parametrize("days", [0, -5, 3651, "abc"])
def test_retention_rejects_bad_values(client, days):
    url = "/admin/settings/retention"
    assert client.put(url, json={"days": days}, headers=SYS).status_code == 422
    assert client.get(url, headers=SYS).json() == {"days": get_settings().retention_days}


def test_retention_change_is_audited(client):
    admin_id = login(client, "admin001", "sys_admin")
    client.put("/admin/settings/retention", json={"days": 30}, headers=SYS)
    entries = client.get("/admin/audit-log", params={"action": "retention_changed"}, headers=SYS)
    assert len(entries.json()) == 1
    assert entries.json()[0]["user_id"] == admin_id
    assert f"{get_settings().retention_days} -> 30" in entries.json()[0]["details"]


def test_retention_job_uses_period_from_database(client, session_factory):
    client.put("/admin/settings/retention", json={"days": 30}, headers=SYS)
    now = datetime.now(UTC)
    with session_factory() as session:
        session.add(
            FoundItem(
                title="Old",
                category=ItemCategory.wallet,
                found_date=now.date(),
                location=CampusLocation.library,
                storage_desk="Desk A",
                storage_cell="Locker 1",
                received_at=now - timedelta(days=40),
                created_by_id=1,
            )
        )
        session.commit()
        # со сроком 90 дней эта вещь не просрочена, со сроком 30 из базы просрочена
        assert mark_overdue_items(session, now=now) == 1
