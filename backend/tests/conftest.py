import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

import app.core.database as db_module
from app.models import Base
from app.main import app
from app.auth import get_current_user, Role
from app.core.database import get_db

# Shared-cache in-memory SQLite so each SessionLocal() gets its own connection
# (required for concurrency tests). StaticPool forces all threads onto one
# connection, which races under concurrent verify_face calls.
_TEST_DB_URL = "sqlite:///file:examguard_test?mode=memory&cache=shared&uri=true"
_test_engine = create_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False, "uri": True},
    poolclass=NullPool,
)

db_module.engine = _test_engine
db_module.SessionLocal = sessionmaker(bind=_test_engine)
# app.main binds `engine` at import time; re-point it so /health checks the
# test database instead of whatever DATABASE_URL the environment provides.
import app.main as _main_module  # noqa: E402

_main_module.engine = _test_engine
# Hold a connection BEFORE create_all so the shared in-memory DB is not
# dropped when create_all's temporary connection closes.
_keepalive = _test_engine.connect()
Base.metadata.create_all(_test_engine)


@pytest.fixture(scope="session")
def engine():
    yield _test_engine
    _keepalive.close()
    _test_engine.dispose()


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
def _override_db(engine):
    """Route API get_db() to the in-memory SQLite test database."""
    TestingSessionLocal = sessionmaker(bind=engine)

    def _test_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _test_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear global face-verification rate limits between tests."""
    from app.services.identity_verification import get_rate_limiter
    get_rate_limiter().reset()
    yield
    get_rate_limiter().reset()


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
