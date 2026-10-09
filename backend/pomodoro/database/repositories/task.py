"""SQLModel implementation of `TaskRepository` (ADR-0002)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlmodel import Session, select

from pomodoro.core.tasks import Task, TaskId, TaskRepository
from pomodoro.core.users import UserId
from pomodoro.database.models.pomodoro import PomodoroTable
from pomodoro.database.models.task import TaskTable
from pomodoro.database.session import get_db_session

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime


class SqlTaskRepository:
    """`TaskRepository` backed by the `task` SQLModel table, scoped to a `UserId`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: Task, text_key: str) -> None:
        """Insert a new `task` row and commit."""
        self._session.add(
            TaskTable(
                id=task.id,
                user_id=task.user_id,
                text=task.text,
                text_key=text_key,
                position=task.position,
                created_at=task.created_at,
                archived_at=task.archived_at,
            )
        )
        self._session.commit()

    def get_by_id(self, user_id: UserId, task_id: TaskId) -> Task | None:
        """Return the caller's Task with this id, or None if absent or owned by another User."""
        row = self._session.get(TaskTable, task_id)
        if row is None or row.user_id != user_id:
            return None
        return _to_entity(row)

    def list_active(self, user_id: UserId) -> list[Task]:
        """Return the caller's Active Tasks ordered by `(position, id)`."""
        rows = self._session.exec(
            select(TaskTable)
            .where(
                TaskTable.user_id == user_id,
                TaskTable.archived_at.is_(None),  # pyrefly: ignore[missing-attribute]
            )
            .order_by(TaskTable.position, TaskTable.id)  # pyrefly: ignore[bad-argument-type]
        ).all()
        return [_to_entity(row) for row in rows]

    def update_text(self, user_id: UserId, task_id: TaskId, text: str, text_key: str) -> None:
        """Overwrite a Task's text and derived key."""
        row = self._session.get(TaskTable, task_id)
        if row is None or row.user_id != user_id:
            return
        row.text = text
        row.text_key = text_key
        self._session.add(row)
        self._session.commit()

    def list_archived(self, user_id: UserId) -> list[Task]:
        """Return the caller's Archived Tasks ordered by `archived_at` descending."""
        rows = self._session.exec(
            select(TaskTable)
            .where(
                TaskTable.user_id == user_id,
                TaskTable.archived_at.is_not(None),  # pyrefly: ignore[missing-attribute]
            )
            .order_by(TaskTable.archived_at.desc())  # pyrefly: ignore[missing-attribute]
        ).all()
        return [_to_entity(row) for row in rows]

    def count_active(self, user_id: UserId) -> int:
        """Return the number of the caller's Active Tasks."""
        return len(
            self._session.exec(
                select(TaskTable.id).where(
                    TaskTable.user_id == user_id,
                    TaskTable.archived_at.is_(None),  # pyrefly: ignore[missing-attribute]
                )
            ).all()
        )

    def count_archived(self, user_id: UserId) -> int:
        """Return the number of the caller's Archived Tasks."""
        return len(
            self._session.exec(
                select(TaskTable.id).where(
                    TaskTable.user_id == user_id,
                    TaskTable.archived_at.is_not(None),  # pyrefly: ignore[missing-attribute]
                )
            ).all()
        )

    def archive(self, user_id: UserId, task_id: TaskId, archived_at: datetime) -> None:
        """Freeze `position` and set `archived_at` on the caller's Task."""
        row = self._session.get(TaskTable, task_id)
        if row is None or row.user_id != user_id:
            return
        row.archived_at = archived_at
        self._session.add(row)
        self._session.commit()

    def unarchive(self, user_id: UserId, task_id: TaskId, position: int) -> None:
        """Clear `archived_at` and set the caller's Task to `position`."""
        row = self._session.get(TaskTable, task_id)
        if row is None or row.user_id != user_id:
            return
        row.archived_at = None
        row.position = position
        self._session.add(row)
        self._session.commit()

    def reorder(self, user_id: UserId, ordered_task_ids: Sequence[TaskId]) -> None:
        """Rewrite the caller's Active Tasks' `position` as `0..n-1`, following this order."""
        rows_by_id = {
            row.id: row
            for row in self._session.exec(
                select(TaskTable).where(
                    TaskTable.user_id == user_id,
                    TaskTable.archived_at.is_(None),  # pyrefly: ignore[missing-attribute]
                )
            ).all()
        }
        for position, task_id in enumerate(ordered_task_ids):
            row = rows_by_id.get(task_id)
            if row is not None:
                row.position = position
                self._session.add(row)
        self._session.commit()

    def delete(self, user_id: UserId, task_id: TaskId) -> None:
        """Permanently remove the caller's Task."""
        row = self._session.get(TaskTable, task_id)
        if row is None or row.user_id != user_id:
            return
        self._session.delete(row)
        self._session.commit()

    def task_ids_with_pomodoros(self, user_id: UserId) -> frozenset[TaskId]:
        """Return the ids of the caller's Tasks that have at least one Pomodoro recorded."""
        rows = self._session.exec(
            select(PomodoroTable.task_id).where(PomodoroTable.user_id == user_id)
        ).all()
        return frozenset(TaskId(task_id) for task_id in rows)


def _to_entity(row: TaskTable) -> Task:
    return Task(
        id=TaskId(row.id),
        user_id=UserId(row.user_id),
        text=row.text,
        position=row.position,
        tag_ids=(),
        created_at=row.created_at,
        archived_at=row.archived_at,
    )


def get_task_repository(session: Session = Depends(get_db_session)) -> TaskRepository:
    """FastAPI provider: a `TaskRepository` backed by the request's DB session."""
    return SqlTaskRepository(session)
