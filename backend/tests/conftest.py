import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db
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


@pytest.fixture
def client(session_factory, photo_store):
    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_photo_store] = lambda: photo_store
    yield TestClient(app)
    app.dependency_overrides.clear()
