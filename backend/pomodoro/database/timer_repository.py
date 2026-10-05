"""SQLModel-backed `TimerRepository` Protocol implementation.

Every User has at most one `timer` row (the table's primary key is
`user_id`); `save` upserts it in place rather than ever inserting a second row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pomodoro.core.entities import TaskId, UserId
from pomodoro.core.timer import BreakKind, Timer, TimerPhase
from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _to_entity(row: tables.Timer) -> Timer:
    return Timer(
        user_id=UserId(row.user_id),
        phase=TimerPhase(row.phase),
        task_id=TaskId(row.task_id) if row.task_id is not None else None,
        break_kind=BreakKind(row.break_kind) if row.break_kind is not None else None,
        phase_started_at=row.phase_started_at,
        accumulated_active_seconds=row.accumulated_active_seconds,
        running_since=row.running_since,
    )


class SQLTimerRepository:
    """`TimerRepository` Protocol implementation backed by a SQLModel engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, user_id: UserId) -> Timer | None:
        with session_scope(self._engine) as session:
            row = session.get(tables.Timer, user_id)
            if row is None:
                return None
            return _to_entity(row)

    def save(self, user_id: UserId, timer: Timer) -> None:
        with session_scope(self._engine) as session:
            row = session.get(tables.Timer, user_id)
            if row is None:
                row = tables.Timer(user_id=user_id, phase=timer.phase.value)
            row.phase = timer.phase.value
            row.task_id = timer.task_id
            row.break_kind = timer.break_kind.value if timer.break_kind is not None else None
            row.phase_started_at = timer.phase_started_at
            row.accumulated_active_seconds = timer.accumulated_active_seconds
            row.running_since = timer.running_since
            session.add(row)
            session.commit()
