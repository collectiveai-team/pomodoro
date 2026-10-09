"""SQLModel-backed `core.repositories.TimerRepository` (CES-18, T13).

The only place a `tables.Timer` row is mapped to a `core.entities.Timer`
dataclass. `apply` is the sole mutation entrypoint: it reads the User's Timer
row (creating an Idle one lazily on first touch), runs the caller's pure
`mutate` against the dataclass snapshot, and persists the result with a
single `UPDATE ... WHERE version = <version just read>`. If a concurrent
writer already advanced the row's `version`, the conditional `UPDATE` affects
zero rows and `apply` retries `mutate` against a freshly re-read row instead
of silently overwriting the other writer's commit - the guard against a known
duplicate-completion bug where two simultaneous requests, both observing a
Pomodoro past its deadline, each persisted their own completed-Pomodoro row
for the same run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from pomodoro.core.entities import BreakKind, TaskId, Timer, TimerPhase, UserId
from pomodoro.database import tables
from pomodoro.database.timestamps import as_utc

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlmodel import Session

    from pomodoro.core.timer import TimerUpdate


def _to_entity(row: tables.Timer) -> Timer:
    return Timer(
        user_id=UserId(row.user_id),
        phase=TimerPhase(row.phase),
        task_id=TaskId(row.task_id) if row.task_id is not None else None,
        break_kind=BreakKind(row.break_kind) if row.break_kind is not None else None,
        phase_started_at=as_utc(row.phase_started_at) if row.phase_started_at is not None else None,
        accumulated_active_seconds=row.accumulated_active_seconds,
        running_since=as_utc(row.running_since) if row.running_since is not None else None,
        phase_ended_at=as_utc(row.phase_ended_at) if row.phase_ended_at is not None else None,
    )


@dataclass
class SqlTimerRepository:
    """`core.repositories.TimerRepository` implementation over a SQLModel `Session`."""

    _session: Session

    def apply(self, user_id: UserId, mutate: Callable[[Timer], TimerUpdate]) -> TimerUpdate:
        """Atomically read-mutate-write `user_id`'s Timer; see module docstring."""
        while True:
            row = self._get_or_create_row(user_id)
            current = _to_entity(row)
            update = mutate(current)
            if update.timer == current and update.pomodoro is None:
                return update
            # pyrefly's SQLAlchemy stubs type a mapped column's `==`/`&` as plain `bool`
            # here (unlike the identical idiom on a `Select.where(...)`, which it accepts),
            # so `Update.where(...)`'s stricter `ColumnElement[bool]` overload is flagged
            # even though this is valid, idiomatic SQLAlchemy - a known stub gap, not a
            # defect here.
            outcome = self._session.execute(
                sa.update(tables.Timer)
                .where(
                    (tables.Timer.user_id == user_id)  # pyrefly: ignore[bad-argument-type]
                    & (tables.Timer.version == row.version)
                )
                .values(
                    version=row.version + 1,
                    phase=update.timer.phase.value,
                    task_id=update.timer.task_id,
                    break_kind=(
                        update.timer.break_kind.value
                        if update.timer.break_kind is not None
                        else None
                    ),
                    phase_started_at=update.timer.phase_started_at,
                    accumulated_active_seconds=update.timer.accumulated_active_seconds,
                    running_since=update.timer.running_since,
                    phase_ended_at=update.timer.phase_ended_at,
                )
            )
            # pyrefly's SQLAlchemy stubs type `Session.execute(...)` as the generic
            # `Result`, which lacks `.rowcount` - at runtime this is always the
            # `CursorResult` an UPDATE/DELETE actually returns, which does have it.
            if outcome.rowcount == 0:  # pyrefly: ignore[missing-attribute]
                self._session.rollback()
                continue
            if update.pomodoro is not None:
                draft = update.pomodoro
                self._session.add(
                    tables.Pomodoro(
                        user_id=user_id,
                        task_id=draft.task_id,
                        started_at=draft.started_at,
                        ended_at=draft.ended_at,
                        duration_seconds=draft.duration_seconds,
                        status=draft.status.value,
                    )
                )
            self._session.commit()
            return update

    def _get_or_create_row(self, user_id: UserId) -> tables.Timer:
        row = self._session.get(tables.Timer, user_id, populate_existing=True)
        if row is not None:
            return row
        row = tables.Timer(user_id=user_id, phase=TimerPhase.IDLE.value, version=0)
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError:
            # A concurrent first-ever request for the same User already created the
            # row; fall back to reading what it committed instead of erroring out.
            self._session.rollback()
            row = self._session.get(tables.Timer, user_id, populate_existing=True)
            if row is None:
                raise
            return row
        self._session.refresh(row)
        return row
