"""Unit tests for the engine/session factory: SQLite pragma and aware timestamps."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from pomodoro.database.engine import create_db_engine, session_scope
from pomodoro.database.tables import SQLModel, User

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_sqlite_engine_enforces_foreign_keys(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'pomodoro.db'}")

    with engine.connect() as connection:
        enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()

    assert enabled == 1


@pytest.mark.unit
def test_timestamps_round_trip_as_timezone_aware(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'pomodoro.db'}")
    SQLModel.metadata.create_all(engine)
    created_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    with session_scope(engine) as session:
        user = User(
            email="person@example.com",
            email_key="person@example.com",
            password_hash="hash",
            time_zone="UTC",
            created_at=created_at,
        )
        session.add(user)
        session.commit()
        user_id = user.id

    with session_scope(engine) as session:
        stored = session.get(User, user_id)
        assert stored is not None
        assert stored.created_at.tzinfo is not None
        assert stored.created_at == created_at


@pytest.mark.unit
def test_non_sqlite_url_selects_the_postgresql_dialect() -> None:
    engine = create_db_engine("postgresql+psycopg://user:pass@localhost/db")

    assert engine.dialect.name == "postgresql"
