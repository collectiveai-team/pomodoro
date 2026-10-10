"""Shared fixtures for PostgreSQL integration tests (T19, ADR-0002).

Every fixture here needs a running PostgreSQL instance addressed by a `DATABASE_URL`
environment variable (read directly here, since `tests/` is exempt from CES-76's
settings-module rule); tests `pytest.skip` cleanly when it is absent, so a fresh clone with no
database stays green. The schema is built by running Alembic's migration chain rather than
`SQLModel.metadata.create_all`, so these tests prove the migrations themselves — and so this
file and `test_alembic_upgrade.py` never race to build the same tables two different ways
against the same shared database.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from pomodoro.settings import get_settings
from sqlmodel import Session

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Engine

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Return the integration suite's PostgreSQL URL, skipping cleanly when unset."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("no PostgreSQL DATABASE_URL set")
    return url


def run_alembic_upgrade_head(database_url: str) -> None:
    """Run the full Alembic migration chain against `database_url`.

    `env.py` reads the database URL only via `get_settings()` (CES-76), never a parameter, so
    redirecting a migration run means setting the `POMODORO_DATABASE_URL` env var the settings
    module itself reads, clearing the cached `Settings` before and after so other code keeps
    seeing the real default.
    """
    previous = os.environ.get("POMODORO_DATABASE_URL")
    os.environ["POMODORO_DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(_REPO_ROOT / "alembic.ini")), "head")
    finally:
        if previous is None:
            os.environ.pop("POMODORO_DATABASE_URL", None)
        else:
            os.environ["POMODORO_DATABASE_URL"] = previous
        get_settings.cache_clear()


@pytest.fixture(scope="session")
def postgres_engine(postgres_url: str) -> Engine:
    """Return a session-wide PostgreSQL engine with every migration applied."""
    run_alembic_upgrade_head(postgres_url)
    return build_engine(postgres_url)


@pytest.fixture
def session(postgres_engine: Engine) -> Iterator[Session]:
    """Yield a `Session` whose writes are rolled back after the test.

    Binds the Session to a connection-level transaction via `join_transaction_mode`, so a
    repository's internal `session.commit()` only commits a SAVEPOINT; rolling back the outer
    transaction at teardown discards everything the test wrote, keeping tests independent of
    each other and of execution order against the one shared database.
    """
    connection = postgres_engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        transaction.rollback()
        connection.close()
