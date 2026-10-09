"""Tests for `SqlPomodoroRepository.list_in_range` (T16).

Fetches the UTC range a History query needs via a plain parameterized `WHERE`
clause - no dialect-specific function - so day-grouping can happen in Python
with `zoneinfo` (ADR-0002).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlmodel import Session

from pomodoro.core.entities import PomodoroId, PomodoroStatus, TaskId, UserId
from pomodoro.database import tables
from pomodoro.database.engine import build_engine
from pomodoro.database.pomodoro_repository import SqlPomodoroRepository
from pomodoro.database.tables import SQLModel

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit

_USER = UserId(1)
_OTHER_USER = UserId(2)
_TASK = TaskId(1)
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def engine() -> Engine:
    engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for user_id in (_USER, _OTHER_USER):
            session.add(
                tables.User(
                    id=user_id,
                    email=f"user{user_id}@example.com",
                    email_key=f"user{user_id}@example.com",
                    password_hash="hash",
                    time_zone="UTC",
                    created_at=_EPOCH,
                )
            )
        session.commit()
        session.add(
            tables.Task(
                id=_TASK,
                user_id=_USER,
                text="Write",
                text_key="write",
                position=0,
                created_at=_EPOCH,
            )
        )
        session.commit()
    return engine


def _add_pomodoro(
    engine: Engine,
    pomodoro_id: int,
    *,
    ended_at: datetime,
    user_id: UserId = _USER,
    status: PomodoroStatus = PomodoroStatus.COMPLETED,
) -> None:
    with Session(engine) as session:
        session.add(
            tables.Pomodoro(
                id=pomodoro_id,
                user_id=user_id,
                task_id=_TASK,
                started_at=ended_at,
                ended_at=ended_at,
                duration_seconds=1500,
                status=status.value,
            )
        )
        session.commit()


class TestListInRange:
    def test_returns_rows_ending_within_the_half_open_range(self, engine: Engine) -> None:
        _add_pomodoro(engine, 1, ended_at=datetime(2026, 3, 5, 12, 0, tzinfo=UTC))
        _add_pomodoro(engine, 2, ended_at=datetime(2026, 3, 1, 0, 0, tzinfo=UTC))  # lower bound
        _add_pomodoro(engine, 3, ended_at=datetime(2026, 4, 1, 0, 0, tzinfo=UTC))  # excluded end

        with Session(engine) as session:
            result = SqlPomodoroRepository(session).list_in_range(
                _USER,
                datetime(2026, 3, 1, 0, 0, tzinfo=UTC),
                datetime(2026, 4, 1, 0, 0, tzinfo=UTC),
            )

        assert {pomodoro.id for pomodoro in result} == {PomodoroId(1), PomodoroId(2)}

    def test_includes_both_completed_and_interrupted_logged(self, engine: Engine) -> None:
        _add_pomodoro(
            engine,
            1,
            ended_at=datetime(2026, 3, 5, 12, 0, tzinfo=UTC),
            status=PomodoroStatus.INTERRUPTED_LOGGED,
        )

        with Session(engine) as session:
            result = SqlPomodoroRepository(session).list_in_range(
                _USER,
                datetime(2026, 3, 1, tzinfo=UTC),
                datetime(2026, 4, 1, tzinfo=UTC),
            )

        assert len(result) == 1
        assert result[0].status is PomodoroStatus.INTERRUPTED_LOGGED

    def test_never_returns_another_users_pomodoros(self, engine: Engine) -> None:
        _add_pomodoro(
            engine, 1, ended_at=datetime(2026, 3, 5, 12, 0, tzinfo=UTC), user_id=_OTHER_USER
        )

        with Session(engine) as session:
            result = SqlPomodoroRepository(session).list_in_range(
                _USER,
                datetime(2026, 3, 1, tzinfo=UTC),
                datetime(2026, 4, 1, tzinfo=UTC),
            )

        assert result == []
