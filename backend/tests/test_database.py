import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal, engine


class TestDatabaseConnection:
    def test_engine_created(self):
        assert engine is not None

    def test_session_factory_created(self):
        assert SessionLocal is not None

    @pytest.mark.skipif(
        "user:password" in get_settings().DATABASE_URL,
        reason="DATABASE_URL still has default placeholder credentials — configure .env with real PostgreSQL credentials",
    )
    def test_engine_can_connect(self):
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
