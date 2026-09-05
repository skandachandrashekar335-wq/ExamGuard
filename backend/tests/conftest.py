import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


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
