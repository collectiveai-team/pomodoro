"""Shared fixtures: a fake Clock and a FastAPI TestClient on an isolated in-memory database.

Per the Testing Decisions (seam principal: `api` vía HTTP), every unit test drives the real app
through `TestClient` against a fresh SQLite `:memory:` database and a `Clock` advanced by hand —
never real sleeps, never a shared database across tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from pomodoro.core.clock import get_clock
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from pomodoro.database.session import get_db_session
from pomodoro.entrypoints.app import create_app
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

if TYPE_CHECKING:
    from collections.abc import Iterator


class FakeClock:
    """A `Clock` whose `now()` is advanced by hand instead of sleeping (ADR-0003)."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        """Return the frozen/advanced current time."""
        return self._now

    def advance(self, delta: timedelta) -> None:
        """Move time forward by `delta`."""
        self._now += delta


@pytest.fixture
def fake_clock() -> FakeClock:
    """Return a `FakeClock` starting at a fixed, timezone-aware instant."""
    return FakeClock(datetime(2026, 1, 1, tzinfo=UTC))


@pytest.fixture
def client(fake_clock: FakeClock) -> Iterator[TestClient]:
    """Yield a `TestClient` for the real app, wired to a fresh in-memory DB and `fake_clock`."""
    engine = build_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    def _get_test_db_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = _get_test_db_session
    app.dependency_overrides[get_clock] = lambda: fake_clock

    # `base_url="https://..."` so the client's cookie jar honors the session cookie's `Secure`
    # attribute and resends it on later requests, exactly as a real browser would over TLS.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
