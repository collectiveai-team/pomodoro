"""SQLModel-backed `TimerRepository` Protocol implementation.

Every User has at most one `timer` row (the table's primary key is
`user_id`); `save` upserts it in place rather than ever inserting a second row.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import CursorResult
from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col

from pomodoro.core.entities import TaskId, UserId
from pomodoro.core.timer import BreakKind, Timer, TimerPhase
from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from datetime import datetime

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
        phase_ended_at=row.phase_ended_at,
    )


@dataclass(frozen=True)
class _TimerColumns:
    """The mutable `timer` row columns a `Timer` entity maps onto."""

    phase: str
    task_id: TaskId | None
    break_kind: str | None
    phase_started_at: datetime | None
    accumulated_active_seconds: int
    running_since: datetime | None
    phase_ended_at: datetime | None


def _row_fields(timer: Timer) -> _TimerColumns:
    return _TimerColumns(
        phase=timer.phase.value,
        task_id=timer.task_id,
        break_kind=timer.break_kind.value if timer.break_kind is not None else None,
        phase_started_at=timer.phase_started_at,
        accumulated_active_seconds=timer.accumulated_active_seconds,
        running_since=timer.running_since,
        phase_ended_at=timer.phase_ended_at,
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
            else:
                # Every write must advance the same version the CAS path
                # observes. Otherwise a normal action could leave the version
                # unchanged and let a stale settle/log CAS overwrite it.
                row.version += 1
            for field, value in asdict(_row_fields(timer)).items():
                setattr(row, field, value)
            session.add(row)
            session.commit()

    def get_with_version(self, user_id: UserId) -> tuple[Timer, int] | None:
        with session_scope(self._engine) as session:
            row = session.get(tables.Timer, user_id)
            if row is None:
                return None
            return _to_entity(row), row.version

    def save_if_unchanged(self, user_id: UserId, version: int | None, timer: Timer) -> bool:
        with session_scope(self._engine) as session:
            if version is None:
                row = tables.Timer(user_id=user_id, phase=timer.phase.value, version=0)
                for field, value in asdict(_row_fields(timer)).items():
                    setattr(row, field, value)
                session.add(row)
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    return False
                return True
            result = cast(
                "CursorResult[Any]",
                session.execute(
                    sa_update(tables.Timer)
                    .where(
                        col(tables.Timer.user_id) == user_id,
                        col(tables.Timer.version) == version,
                    )
                    .values(version=version + 1, **asdict(_row_fields(timer)))
                ),
            )
            session.commit()
            return result.rowcount == 1
