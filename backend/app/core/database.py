from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Ensure Neon PostgreSQL SSL is always enabled.
# Railway may provide a DATABASE_URL without sslmode; require it here.
_engine_ssl_args = {}
if settings.DATABASE_URL:
    _engine_ssl_args["sslmode"] = "require"

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_engine_ssl_args,
)

SessionLocal = sessionmaker(bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()