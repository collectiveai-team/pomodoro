"""Integration tests: `alembic upgrade head` builds the schema from empty (T19, ADR-0002).

Proves the full migration chain on both engines the app supports: a fresh SQLite file (always
runs — no external service) and real PostgreSQL via `DATABASE_URL` (skips cleanly when that is
not set). Reuses `run_alembic_upgrade_head` from `conftest.py`, the same helper the PostgreSQL
constraint tests use to build their schema, so there is exactly one code path that drives
Alembic in this suite.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine, inspect
from tests.integration.conftest import run_alembic_upgrade_head

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine

pytestmark = pytest.mark.integration

_EXPECTED_TABLES = frozenset(
    {"user", "auth_session", "task", "tag", "task_tags", "pomodoro", "timer"}
)


def _table_names(database_url: str) -> set[str]:
    engine: Engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_alembic_upgrade_head_builds_the_schema_on_a_fresh_sqlite_file(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'pomodoro.db'}"

    run_alembic_upgrade_head(database_url)

    assert _table_names(database_url) >= _EXPECTED_TABLES


def test_alembic_upgrade_head_builds_the_schema_on_a_fresh_postgresql_database() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("no PostgreSQL DATABASE_URL set")

    run_alembic_upgrade_head(database_url)

    assert _table_names(database_url) >= _EXPECTED_TABLES
