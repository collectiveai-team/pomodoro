"""SQLModel-backed Pomodoro persistence.

T9 (Tasks API) added `exists_for_task` as a shared prerequisite for the
"deletable" flag and the permanent-delete guard. T12 (Timer API) completes
the `pomodoro.core.repositories.PomodoroRepository` Protocol here with `add`
(persisting a completed/interrupted-logged Pomodoro), `count_completed_for_user`
(the Break-cadence counter) and `count_completed_between` (the day summary's
timezone-bucketed "completed today" count). T15 (core History rule) adds
`list_between`, fetching every Pomodoro in a UTC range for monthly/day
aggregation.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from sqlmodel import col, func, select

from pomodoro.core.entities import Pomodoro, PomodoroId, PomodoroStatus, TaskId, UserId
from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.engine import Engine


def _require_row_id(row: tables.Pomodoro) -> int:
    if row.id is None:
        raise AssertionError
    return row.id


def _to_entity(row: tables.Pomodoro) -> Pomodoro:
    return Pomodoro(
        id=PomodoroId(_require_row_id(row)),
        user_id=UserId(row.user_id),
        task_id=TaskId(row.task_id),
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_seconds=row.duration_seconds,
        status=PomodoroStatus(row.status),
    )


class SQLPomodoroRepository:
    """`PomodoroRepository` Protocol implementation backed by a SQLModel engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, pomodoro: Pomodoro) -> Pomodoro:
        with session_scope(self._engine) as session:
            row = tables.Pomodoro(
                user_id=pomodoro.user_id,
                task_id=pomodoro.task_id,
                started_at=pomodoro.started_at,
                ended_at=pomodoro.ended_at,
                duration_seconds=pomodoro.duration_seconds,
                status=pomodoro.status.value,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return replace(pomodoro, id=PomodoroId(_require_row_id(row)))

    def count_completed_for_user(self, user_id: UserId) -> int:
        with session_scope(self._engine) as session:
            return session.exec(
                select(func.count())
                .select_from(tables.Pomodoro)
                .where(
                    tables.Pomodoro.user_id == user_id,
                    tables.Pomodoro.status == PomodoroStatus.COMPLETED.value,
                )
            ).one()

    def count_completed_between(self, user_id: UserId, start: datetime, end: datetime) -> int:
        with session_scope(self._engine) as session:
            return session.exec(
                select(func.count())
                .select_from(tables.Pomodoro)
                .where(
                    tables.Pomodoro.user_id == user_id,
                    tables.Pomodoro.status == PomodoroStatus.COMPLETED.value,
                    tables.Pomodoro.ended_at >= start,
                    tables.Pomodoro.ended_at < end,
                )
            ).one()

    def exists_for_task(self, user_id: UserId, task_id: TaskId) -> bool:
        with session_scope(self._engine) as session:
            row = session.exec(
                select(tables.Pomodoro.id).where(
                    tables.Pomodoro.user_id == user_id, tables.Pomodoro.task_id == task_id
                )
            ).first()
            return row is not None

    def list_between(self, user_id: UserId, start: datetime, end: datetime) -> list[Pomodoro]:
        with session_scope(self._engine) as session:
            rows = session.exec(
                select(tables.Pomodoro)
                .where(
                    tables.Pomodoro.user_id == user_id,
                    tables.Pomodoro.ended_at >= start,
                    tables.Pomodoro.ended_at < end,
                )
                .order_by(col(tables.Pomodoro.ended_at))
            ).all()
            return [_to_entity(row) for row in rows]
