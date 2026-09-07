import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.main import app
from app.auth import get_current_user, Role


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture()
def SessionLocal(engine):
    """Provide a SessionLocal-compatible factory backed by the test engine."""
    return sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _override_auth():
    """Override auth dependency for all tests — bypass JWT validation."""
    def _fake_user():
        return {
            "sub": "1",
            "role": Role.ADMIN,
            "email": "test@example.com",
            "full_name": "Test User",
        }
    app.dependency_overrides[get_current_user] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client():
    return TestClient(app)
