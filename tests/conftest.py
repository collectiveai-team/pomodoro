"""Shared fixtures for HTTP-level API tests (`test_*_api.py`).

Every such module backs its `TestClient` with a `tmp_path` SQLite file rather
than `sqlite:///:memory:`, because `TestClient` dispatches each request on its
own worker thread and `:memory:` is private to the connection that opened it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from pomodoro.api import session, tasks, timer
from pomodoro.database.auth_session_repository import SQLAuthSessionRepository
from pomodoro.database.engine import create_db_engine
from pomodoro.database.pomodoro_repository import SQLPomodoroRepository
from pomodoro.database.tables import SQLModel
from pomodoro.database.tag_repository import SQLTagRepository
from pomodoro.database.task_repository import SQLTaskRepository
from pomodoro.database.timer_repository import SQLTimerRepository
from pomodoro.database.user_repository import SQLUserRepository
from pomodoro.entrypoints.app import create_app

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


def build_tasks_client(engine: Engine, clock: FakeClock) -> TestClient:
    """Build a `TestClient` wired for the Tasks/Timer API routers, shared across `test_*_api.py`."""
    app = create_app()
    app.dependency_overrides.update(
        {
            session.get_clock: lambda: clock,
            session.get_user_repository: lambda: SQLUserRepository(engine),
            session.get_auth_session_repository: lambda: SQLAuthSessionRepository(engine, clock),
            tasks.get_task_repository: lambda: SQLTaskRepository(engine),
            tasks.get_tag_repository: lambda: SQLTagRepository(engine),
            tasks.get_pomodoro_repository: lambda: SQLPomodoroRepository(engine),
            timer.get_timer_repository: lambda: SQLTimerRepository(engine),
        }
    )
    return TestClient(app)


@dataclass
class AuthedSession:
    """A ready-to-use client plus the state behind its cookie, for one test."""

    client: TestClient
    clock: FakeClock
    engine: Engine
    cookies: dict[str, str]
    user_id: int


def authed_session(
    tmp_path: Path,
    *,
    email: str = "person@example.com",
    password: str = TEST_PASSWORD,
    time_zone: str = "America/Argentina/Buenos_Aires",
) -> AuthedSession:
    engine = http_test_engine(tmp_path)
    clock = FakeClock()
    client = build_tasks_client(engine, clock)
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "time_zone": time_zone},
    )
    assert response.status_code == 201
    cookies = {session.SESSION_COOKIE_NAME: response.cookies[session.SESSION_COOKIE_NAME]}
    return AuthedSession(
        client=client, clock=clock, engine=engine, cookies=cookies, user_id=response.json()["id"]
    )


def as_other_user(
    s: AuthedSession, *, email: str = "other@example.com"
) -> tuple[TestClient, dict[str, str]]:
    """Register a second User sharing `s`'s database and return their own client+cookies."""
    other_client = build_tasks_client(s.engine, s.clock)
    register = other_client.post(
        "/api/auth/register",
        json={"email": email, "password": TEST_PASSWORD, "time_zone": "UTC"},
    )
    cookies = {session.SESSION_COOKIE_NAME: register.cookies[session.SESSION_COOKIE_NAME]}
    return other_client, cookies
