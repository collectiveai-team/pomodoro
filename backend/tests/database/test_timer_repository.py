"""Repository tests for persisted Timer state and recorded Pomodoros (T11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import BreakKind, Pomodoro, PomodoroStatus, Timer, TimerPhase
from pomodoro.core.users import UserId
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from pomodoro.database.models.task import TaskTable
from pomodoro.database.models.user import UserTable
from pomodoro.database.repositories.pomodoro import SqlPomodoroRepository
from pomodoro.database.repositories.timer import SqlTimerRepository
from pomodoro.entrypoints.app import create_app
from pomodoro.entrypoints.clock import SystemClock
from sqlmodel import Session, SQLModel

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = pytest.mark.unit


@pytest.fixture
def session() -> Generator[Session]:
    """Return an isolated SQLite session containing the production schema."""
    engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def user_and_task_id(session: Session) -> tuple[UserId, TaskId]:
    """Persist a User and one Task so repository rows satisfy their foreign keys."""
    user_id = UserId(uuid4())
    task_id = TaskId(uuid4())
    now = datetime(2026, 1, 1, tzinfo=UTC)
    session.add(
        UserTable(
            id=user_id,
            email="timer-owner@example.com",
            email_key="timer-owner@example.com",
            password_hash="hash",
            time_zone="UTC",
            created_at=now,
        )
    )
    session.commit()
    session.add(
        TaskTable(
            id=task_id,
            user_id=user_id,
            text="Write T11",
            text_key="write t11",
            position=0,
            created_at=now,
        )
    )
    session.commit()
    return user_id, task_id


def test_timer_and_pomodoro_repositories_round_trip_for_one_user(
    session: Session, user_and_task_id: tuple[UserId, TaskId]
) -> None:
    """Timer state and complete record values survive SQLite persistence as UTC dataclasses."""
    user_id, task_id = user_and_task_id
    started_at = datetime(2026, 1, 1, 9, tzinfo=UTC)
    timer = Timer(
        phase=TimerPhase.BREAK_PAUSED,
        task_id=task_id,
        break_kind=BreakKind.LONG,
        phase_started_at=started_at,
        accumulated_active_seconds=120,
    )
    pomodoro = Pomodoro(
        task_id=task_id,
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=25),
        duration_seconds=25 * 60,
        status=PomodoroStatus.COMPLETED,
    )

    timer_repository = SqlTimerRepository(session)
    pomodoro_repository = SqlPomodoroRepository(session)
    timer_repository.save(user_id, timer)
    pomodoro_repository.add(user_id, pomodoro)

    assert timer_repository.get(user_id) == timer
    assert pomodoro_repository.list_for_user(user_id) == [pomodoro]


def test_system_clock_returns_a_timezone_aware_utc_time() -> None:
    """The app's production Clock is aware and normalizes its answer to UTC."""
    now = SystemClock().now()

    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)


def test_app_factory_exposes_its_injected_clock_through_the_health_interface() -> None:
    """The entrypoint's Clock adapter is injected once and read by API dependencies."""
    fixed_now = datetime(2026, 1, 1, 9, tzinfo=UTC)

    class FixedClock:
        def now(self) -> datetime:
            return fixed_now

    client = TestClient(create_app(clock=FixedClock()))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["server_time"] == "2026-01-01T09:00:00Z"
