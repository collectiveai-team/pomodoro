"""Unit tests for the database engine builder (ADR-0002, CES-18)."""

import pytest
from pomodoro.database.engine import build_engine
from sqlalchemy import text

pytestmark = pytest.mark.unit


def test_sqlite_engine_enables_foreign_key_pragma() -> None:
    engine = build_engine("sqlite:///:memory:")

    with engine.connect() as connection:
        fk_enforcement = connection.execute(text("PRAGMA foreign_keys")).scalar_one()

    assert fk_enforcement == 1


def test_postgresql_url_builds_an_engine_without_connecting() -> None:
    engine = build_engine("postgresql+psycopg://user:pass@localhost/pomodoro")

    assert engine.url.drivername == "postgresql+psycopg"


def test_default_database_url_comes_from_settings() -> None:
    from pomodoro.settings import get_settings

    engine = build_engine()

    assert str(engine.url) == get_settings().database_url
