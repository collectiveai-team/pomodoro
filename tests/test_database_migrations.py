"""Proves `alembic upgrade head` builds the full schema from zero.

SQLite is exercised unconditionally; PostgreSQL is exercised too, but only
when a PostgreSQL `DATABASE_URL` is configured in the environment, skipping
cleanly otherwise (no PostgreSQL service is assumed to be running locally).
"""

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from pomodoro.database.engine import create_db_engine

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "backend" / "pomodoro" / "database" / "migrations"

EXPECTED_TABLES = {"user", "auth_session", "task", "tag", "task_tags", "pomodoro", "timer"}


def _alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.mark.unit
def test_alembic_upgrade_head_creates_full_schema_on_fresh_sqlite(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'pomodoro.db'}"

    command.upgrade(_alembic_config(database_url), "head")

    engine = create_db_engine(database_url)
    with engine.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names())
    assert tables >= EXPECTED_TABLES


@pytest.mark.unit
def test_alembic_downgrade_from_head_drops_every_table(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'pomodoro.db'}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    command.downgrade(config, "base")

    engine = create_db_engine(database_url)
    with engine.connect() as connection:
        tables = set(sa.inspect(connection).get_table_names())
    assert not (EXPECTED_TABLES & tables)


@pytest.mark.integration
def test_alembic_upgrade_head_creates_full_schema_on_fresh_postgresql() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("No PostgreSQL DATABASE_URL configured")

    config = _alembic_config(database_url)
    command.downgrade(config, "base")
    try:
        command.upgrade(config, "head")

        engine = create_db_engine(database_url)
        with engine.connect() as connection:
            tables = set(sa.inspect(connection).get_table_names())
        assert tables >= EXPECTED_TABLES
    finally:
        command.downgrade(config, "base")
