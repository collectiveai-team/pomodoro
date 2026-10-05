"""Shared fixtures for HTTP-level API tests (`test_*_api.py`).

Every such module backs its `TestClient` with a `tmp_path` SQLite file rather
than `sqlite:///:memory:`, because `TestClient` dispatches each request on its
own worker thread and `:memory:` is private to the connection that opened it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pomodoro.database.engine import create_db_engine
from pomodoro.database.tables import SQLModel

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine import Engine

NOW = datetime(2026, 1, 1, tzinfo=UTC)
TEST_PASSWORD = "correct horse"


@dataclass
class FakeClock:
    """A `Clock` advanced by hand, standing in for the real wall clock in tests."""

    current: datetime = NOW

    def advance(self, seconds: float) -> datetime:
        self.current += timedelta(seconds=seconds)
        return self.current

    def now(self) -> datetime:
        return self.current


def http_test_engine(tmp_path: Path) -> Engine:
    """Build a fresh file-backed SQLite engine with every table created."""
    db_path = tmp_path / "pomodoro.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    return engine
