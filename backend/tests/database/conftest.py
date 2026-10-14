"""Shared fixtures for database repository tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from sqlmodel import Session, SQLModel

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def session() -> Generator[Session]:
    """Return an isolated SQLite session containing the production schema."""
    engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
