"""SQLModel implementation of `PomodoroRepository` (ADR-0002)."""

from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session, select

from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import Pomodoro, PomodoroRepository, PomodoroStatus
from pomodoro.core.users import UserId
from pomodoro.database.models.pomodoro import PomodoroTable
from pomodoro.database.session import get_db_session
from pomodoro.database.timestamps import as_utc


class SqlPomodoroRepository:
    """`PomodoroRepository` backed by `pomodoro`, always queried by owning User."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user_id: UserId, pomodoro: Pomodoro) -> None:
        """Insert one completed or deliberately logged interrupted Pomodoro and commit."""
        self._session.add(
            PomodoroTable(
                user_id=user_id,
                task_id=pomodoro.task_id,
                started_at=as_utc(pomodoro.started_at),
                ended_at=as_utc(pomodoro.ended_at),
                duration_seconds=pomodoro.duration_seconds,
                status=pomodoro.status.value,
            )
        )
        self._session.commit()

    def list_for_user(self, user_id: UserId) -> list[Pomodoro]:
        """Return this User's Pomodoros by completion time, never another User's rows."""
        rows = self._session.exec(
            select(PomodoroTable)
            .where(PomodoroTable.user_id == user_id)
            .order_by(PomodoroTable.ended_at, PomodoroTable.id)  # pyrefly: ignore[bad-argument-type]
        ).all()
        return [_to_entity(row) for row in rows]


def _to_entity(row: PomodoroTable) -> Pomodoro:
    """Convert a database-only row into a framework-free recorded Pomodoro."""
    return Pomodoro(
        task_id=TaskId(row.task_id),
        started_at=as_utc(row.started_at),
        ended_at=as_utc(row.ended_at),
        duration_seconds=row.duration_seconds,
        status=PomodoroStatus(row.status),
    )


def get_pomodoro_repository(session: Session = Depends(get_db_session)) -> PomodoroRepository:
    """FastAPI provider: a `PomodoroRepository` backed by the request's DB session."""
    return SqlPomodoroRepository(session)
