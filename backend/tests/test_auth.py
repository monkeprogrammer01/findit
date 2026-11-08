import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.auth.fake_sso import TEST_USERS, issue_token
from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_no_token_returns_401(client):
    assert client.get("/me").status_code == 401


def test_garbage_token_returns_401(client):
    assert client.get("/me", headers=auth("not-a-jwt")).status_code == 401


def test_expired_token_returns_401(client):
    token = issue_token(TEST_USERS["student"], "student", expires_in=-10)
    assert client.get("/me", headers=auth(token)).status_code == 401


def test_valid_token_returns_current_user(client):
    token = issue_token(TEST_USERS["desk_admin"], "desk_admin")
    response = client.get("/me", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["campus_id"] == TEST_USERS["desk_admin"]
    assert response.json()["role"] == "desk_admin"


def test_first_login_creates_user_once(client):
    token = issue_token(TEST_USERS["student"], "student")
    first = client.get("/me", headers=auth(token)).json()
    second = client.get("/me", headers=auth(token)).json()
    assert first["id"] == second["id"]


def test_dev_sso_issues_token_that_works(client):
    token = client.post("/dev-sso/token", params={"role": "sys_admin"}).json()["access_token"]
    response = client.get("/me", headers=auth(token))
    assert response.json()["role"] == "sys_admin"
