"""Unit tests for the real (not stubbed) DB-session dependency provider."""

from __future__ import annotations

import pytest
from sqlmodel import select

from pomodoro.database.engine import build_engine
from pomodoro.entrypoints import dependencies
from pomodoro.entrypoints.settings import get_settings

pytestmark = pytest.mark.unit


def test_build_engine_opens_a_working_sqlite_connection() -> None:
    engine = build_engine("sqlite://")

    with engine.connect() as connection:
        assert connection.exec_driver_sql("select 1").scalar_one() == 1


def test_get_db_session_yields_a_working_session_and_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    get_settings.cache_clear()
    dependencies.get_engine.cache_clear()
    try:
        session_iter = dependencies.get_db_session()
        session = next(session_iter)

        assert session.exec(select(1)).one() == 1

        with pytest.raises(StopIteration):
            next(session_iter)
    finally:
        get_settings.cache_clear()
        dependencies.get_engine.cache_clear()
