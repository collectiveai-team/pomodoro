"""SQLModel-backed Pomodoro persistence.

Shared prerequisite for T9 (Tasks API): the "deletable" flag and the
permanent-delete guard both need to know whether a Task has any recorded
Pomodoro. Only `exists_for_task` is implemented here; `add` and
`count_completed_for_user` -- the rest of
`pomodoro.core.repositories.PomodoroRepository` -- are T12's (Timer API) to
add.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from pomodoro.core.entities import TaskId, UserId


class SQLPomodoroRepository:
    """Partial `PomodoroRepository` Protocol implementation backed by a SQLModel engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def exists_for_task(self, user_id: UserId, task_id: TaskId) -> bool:
        with session_scope(self._engine) as session:
            row = session.exec(
                select(tables.Pomodoro.id).where(
                    tables.Pomodoro.user_id == user_id, tables.Pomodoro.task_id == task_id
                )
            ).first()
            return row is not None
