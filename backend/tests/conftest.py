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
from pomodoro.api.v1.dependencies import get_clock
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from pomodoro.database.session import get_db_session
from pomodoro.entrypoints.app import create_app
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Engine


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
def db_engine() -> Engine:
    """Return a fresh in-memory engine with every table created, shared by `client`.

    Exposed separately so a test can reach into the database directly for state the API itself
    has no endpoint for yet (e.g. inserting a `pomodoro` row before the Timer ticket lands).
    """
    engine = build_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine: Engine, fake_clock: FakeClock) -> Iterator[TestClient]:
    """Yield a `TestClient` for the real app, wired to `db_engine` and `fake_clock`."""

    def _get_test_db_session() -> Iterator[Session]:
        with Session(db_engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = _get_test_db_session
    app.dependency_overrides[get_clock] = lambda: fake_clock

    # `base_url="https://..."` so the client's cookie jar honors the session cookie's `Secure`
    # attribute and resends it on later requests, exactly as a real browser would over TLS.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


def register_user(client: TestClient, *, email: str = "owner@example.com") -> None:
    """Register a User through the API with a fixed password and time zone."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
    )


def create_task(client: TestClient, text: str) -> str:
    """Create a Task through the API and return its id."""
    response = client.post("/api/v1/tasks", json={"text": text})
    assert response.status_code == 201
    return response.json()["id"]
