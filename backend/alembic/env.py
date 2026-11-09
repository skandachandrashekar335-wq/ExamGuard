from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.models import Base  # noqa: F401 — Base.metadata is the migration target
import app.models  # noqa: F401 — ensure all model modules are imported

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = settings.DATABASE_URL or config.get_main_option("sqlalchemy.url")
    connect_args = {}
    if "postgres" in url.lower():
        if not ("localhost" in url.lower() or "127.0.0.1" in url.lower() or "sslmode=disable" in url.lower()):
            connect_args["sslmode"] = "require"
    connectable = create_engine(url, connect_args=connect_args)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
