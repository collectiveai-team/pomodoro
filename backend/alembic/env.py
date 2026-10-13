"""Alembic migration environment (ADR-0002, CES-18).

The database URL comes from the CES-76 settings module (`get_settings().database_url`), never
from a hand-rolled `alembic.ini` value or `os.environ` read here.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from pomodoro.settings import get_settings
from sqlmodel import SQLModel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit migration SQL to the script output without a live DB connection."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection, built via the database layer's engine.

    Reusing `build_engine` keeps the Alembic connection on the same code path as the app's
    engine (SQLite foreign-key pragma, local `.tmp` directory creation). SQLite's `ALTER TABLE`
    support is limited, so batch mode (which rebuilds the table under a temporary name) is
    enabled only for that dialect.
    """
    connectable = build_engine(get_settings().database_url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
