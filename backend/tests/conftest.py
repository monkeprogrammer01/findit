import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db
from app.infrastructure.notifications.gateway import get_notifier
from app.infrastructure.storage.photos import LocalPhotoStore, get_photo_store
from app.main import app


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def photo_store(tmp_path):
    return LocalPhotoStore(tmp_path / "photos")


class FakeNotifier:
    """Вместо SMTP: сообщения только складываются в список, ничего не отправляется."""

    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)

    def to(self, email: str) -> list[str]:
        return [m.subject for m in self.sent if m.to_email == email]


@pytest.fixture
def notifier():
    return FakeNotifier()


@pytest.fixture
def client(session_factory, photo_store, notifier):
    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_photo_store] = lambda: photo_store
    app.dependency_overrides[get_notifier] = lambda: notifier
    yield TestClient(app)
    app.dependency_overrides.clear()
