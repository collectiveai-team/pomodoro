"""SQLModel implementation of `TimerRepository` (ADR-0002, ADR-0003)."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from fastapi import Depends
from sqlmodel import Session

from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import BreakKind, Pomodoro, Timer, TimerPhase, TimerRepository
from pomodoro.core.users import UserId
from pomodoro.database.models.pomodoro import PomodoroTable
from pomodoro.database.models.timer import TimerTable
from pomodoro.database.session import get_db_session
from pomodoro.database.timestamps import as_utc


class SqlTimerRepository:
    """`TimerRepository` backed by the one-row-per-User `timer` table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: UserId) -> Timer | None:
        """Return `user_id`'s saved Timer, if present."""
        row = self._session.get(TimerTable, user_id)
        return None if row is None else _to_entity(row)

    def save(self, user_id: UserId, timer: Timer) -> None:
        """Upsert `user_id`'s Timer, keeping one durable row per User."""
        self._save_row(user_id, timer)
        self._session.commit()

    def save_completed_settlement(
        self, user_id: UserId, timer: Timer, completed_pomodoro: Pomodoro
    ) -> None:
        """Commit a lazy completion and its resulting Timer state as one transaction."""
        self._save_row(user_id, timer)
        self._session.add(
            PomodoroTable(
                user_id=user_id,
                task_id=completed_pomodoro.task_id,
                started_at=as_utc(completed_pomodoro.started_at),
                ended_at=as_utc(completed_pomodoro.ended_at),
                duration_seconds=completed_pomodoro.duration_seconds,
                status=completed_pomodoro.status.value,
            )
        )
        self._session.commit()

    def _save_row(self, user_id: UserId, timer: Timer) -> None:
        """Stage the one Timer row without committing, for single or atomic writes."""
        row = self._session.get(TimerTable, user_id)
        if row is None:
            row = TimerTable(user_id=user_id, phase=timer.phase.value)
        row.phase = timer.phase.value
        row.task_id = timer.task_id
        row.break_kind = timer.break_kind.value if timer.break_kind is not None else None
        row.phase_started_at = _optional_as_utc(timer.phase_started_at)
        row.accumulated_active_seconds = timer.accumulated_active_seconds
        row.running_since = _optional_as_utc(timer.running_since)
        self._session.add(row)


def _optional_as_utc(value: datetime | None) -> datetime | None:
    """Normalize a possibly absent timestamp without widening the public repository interface."""
    return None if value is None else as_utc(value)


def _to_entity(row: TimerTable) -> Timer:
    """Convert a SQLModel row into the core's framework-free Timer dataclass."""
    return Timer(
        phase=TimerPhase(row.phase),
        task_id=cast("TaskId | None", row.task_id),
        break_kind=BreakKind(row.break_kind) if row.break_kind is not None else None,
        phase_started_at=_optional_as_utc(row.phase_started_at),
        accumulated_active_seconds=row.accumulated_active_seconds,
        running_since=_optional_as_utc(row.running_since),
    )


def get_timer_repository(session: Session = Depends(get_db_session)) -> TimerRepository:
    """FastAPI provider: a `TimerRepository` backed by the request's DB session."""
    return SqlTimerRepository(session)
