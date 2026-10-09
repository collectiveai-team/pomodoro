"""SQLModel implementation of `TaskRepository` (ADR-0002)."""

from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session, select

from pomodoro.core.tasks import Task, TaskId, TaskRepository
from pomodoro.core.users import UserId
from pomodoro.database.models.task import TaskTable
from pomodoro.database.session import get_db_session


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
