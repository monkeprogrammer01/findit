import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.auth.fake_sso import TEST_USERS, issue_token
from app.infrastructure.db.models import AuditLog, User
from app.infrastructure.db.session import get_db
from app.interface.api.deps import DeskAdmin, SysAdmin

# Маленькое приложение с «админскими» маршрутами только для проверки ролей.
# Настоящие админские эндпоинты появятся в других задачах и будут устроены так же.
probe = FastAPI()


@probe.get("/desk-only")
def desk_only(user: DeskAdmin):
    return {"secret": "claim answers"}


@probe.get("/sys-only")
def sys_only(user: SysAdmin):
    return {"secret": "audit log"}


@pytest.fixture
def probe_client(session_factory):
    def override_get_db():
        with session_factory() as session:
            yield session

    probe.dependency_overrides[get_db] = override_get_db
    yield TestClient(probe)
    probe.dependency_overrides.clear()


def headers_for(role: str) -> dict:
    token = issue_token(TEST_USERS[role], role)
    return {"Authorization": f"Bearer {token}"}


def audit_rows(session_factory) -> list[AuditLog]:
    with session_factory() as session:
        return list(session.scalars(select(AuditLog)))


def test_no_token_returns_401_and_is_not_forbidden(probe_client, session_factory):
    assert probe_client.get("/desk-only").status_code == 401
    assert audit_rows(session_factory) == []


def test_student_cannot_get_admin_data(probe_client):
    response = probe_client.get("/desk-only", headers=headers_for("student"))
    assert response.status_code == 403
    # в ответе нет никаких данных, только общий отказ
    assert response.json() == {"detail": "Forbidden"}
    assert probe_client.get("/sys-only", headers=headers_for("student")).status_code == 403


def test_403_is_written_to_audit_log(probe_client, session_factory):
    probe_client.get("/desk-only", headers=headers_for("student"))

    rows = audit_rows(session_factory)
    assert len(rows) == 1
    entry = rows[0]
    assert entry.action == "forbidden"
    assert entry.method == "GET"
    assert entry.path == "/desk-only"
    assert entry.created_at is not None
    with session_factory() as session:
        student = session.scalar(select(User).where(User.campus_id == TEST_USERS["student"]))
    assert entry.user_id == student.id


def test_every_denied_attempt_is_logged(probe_client, session_factory):
    for _ in range(3):
        probe_client.get("/sys-only", headers=headers_for("student"))
    assert len(audit_rows(session_factory)) == 3


def test_right_role_gets_access_and_nothing_is_logged(probe_client, session_factory):
    assert probe_client.get("/desk-only", headers=headers_for("desk_admin")).status_code == 200
    assert probe_client.get("/sys-only", headers=headers_for("sys_admin")).status_code == 200
    assert audit_rows(session_factory) == []


def test_desk_admin_cannot_use_sys_admin_endpoint(probe_client):
    response = probe_client.get("/sys-only", headers=headers_for("desk_admin"))
    assert response.status_code == 403
