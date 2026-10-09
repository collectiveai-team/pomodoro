"""SQLModel-backed `core.repositories.PomodoroRepository` (CES-18, T13).

Read-only: a finished Pomodoro is always written by `SqlTimerRepository.apply`
in the same transaction as the Timer row it completed or logged (T13), never
through this repository, so a completed-Pomodoro row and its Timer transition
can never be persisted separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import select

from pomodoro.core.entities import Pomodoro, PomodoroId, PomodoroStatus, TaskId, UserId
from pomodoro.database import tables
from pomodoro.database.rows import require_id
from pomodoro.database.timestamps import as_utc

if TYPE_CHECKING:
    from datetime import datetime

    from sqlmodel import Session


def _to_entity(row: tables.Pomodoro) -> Pomodoro:
    return Pomodoro(
        id=PomodoroId(require_id(row.id)),
        user_id=UserId(row.user_id),
        task_id=TaskId(row.task_id),
        started_at=as_utc(row.started_at),
        ended_at=as_utc(row.ended_at),
        duration_seconds=row.duration_seconds,
        status=PomodoroStatus(row.status),
    )


@dataclass
class SqlPomodoroRepository:
    """`core.repositories.PomodoroRepository` implementation over a SQLModel `Session`."""

    _session: Session

    def list_completed(self, user_id: UserId) -> list[Pomodoro]:
        rows = self._session.exec(
            select(tables.Pomodoro).where(
                tables.Pomodoro.user_id == user_id,
                tables.Pomodoro.status == PomodoroStatus.COMPLETED.value,
            )
        ).all()
        return [_to_entity(row) for row in rows]

    def list_in_range(self, user_id: UserId, start: datetime, end: datetime) -> list[Pomodoro]:
        rows = self._session.exec(
            select(tables.Pomodoro).where(
                tables.Pomodoro.user_id == user_id,
                tables.Pomodoro.ended_at >= start,
                tables.Pomodoro.ended_at < end,
            )
        ).all()
        return [_to_entity(row) for row in rows]
