"""SQLModel-backed `core.repositories.TaskRepository` (CES-18, T10/T11).

The only place a `tables.Task` row is mapped to a `core.entities.Task`
dataclass: every method here returns the dataclass, never the row or a raw
dict (CES-79, ADR-0002). Every method takes the owning `UserId` explicitly and
filters by it in the query itself, so cross-User leakage is impossible by
construction rather than relying on a caller to double-check ownership.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from pomodoro.core.entities import TagId, Task, TaskId, UserId
from pomodoro.core.errors import DuplicateTaskTextError
from pomodoro.core.normalization import task_text_key
from pomodoro.database import tables
from pomodoro.database.rows import require_id
from pomodoro.database.timestamps import as_utc

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from sqlmodel import Session


def _tag_ids_by_task(session: Session, task_ids: Iterable[int]) -> Mapping[int, frozenset[TagId]]:
    ids = list(task_ids)
    grouped: dict[int, set[TagId]] = {}
    if ids:
        rows = session.exec(select(tables.TaskTags).where(tables.TaskTags.task_id.in_(ids))).all()
        for row in rows:
            grouped.setdefault(row.task_id, set()).add(TagId(row.tag_id))
    return {task_id: frozenset(tag_ids) for task_id, tag_ids in grouped.items()}


def _to_entity(row: tables.Task, *, tag_ids: frozenset[TagId] = frozenset()) -> Task:
    return Task(
        id=TaskId(require_id(row.id)),
        user_id=UserId(row.user_id),
        text=row.text,
        position=row.position,
        created_at=as_utc(row.created_at),
        archived_at=as_utc(row.archived_at) if row.archived_at is not None else None,
        tag_ids=tag_ids,
    )


@dataclass
class SqlTaskRepository:
    """`core.repositories.TaskRepository` implementation over a SQLModel `Session`."""

    _session: Session

    def add(self, *, user_id: UserId, text: str, position: int, created_at: datetime) -> Task:
        row = tables.Task(
            user_id=user_id,
            text=text,
            text_key=task_text_key(text),
            position=position,
            created_at=created_at,
        )
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateTaskTextError(text) from exc
        self._session.refresh(row)
        return _to_entity(row)

    def list_for_user(self, user_id: UserId) -> list[Task]:
        rows = self._session.exec(select(tables.Task).where(tables.Task.user_id == user_id)).all()
        tag_ids_by_task = _tag_ids_by_task(self._session, (require_id(row.id) for row in rows))
        return [
            _to_entity(row, tag_ids=tag_ids_by_task.get(require_id(row.id), frozenset()))
            for row in rows
        ]

    def get(self, user_id: UserId, task_id: TaskId) -> Task | None:
        row = self._get_row(user_id, task_id)
        if row is None:
            return None
        tag_ids = _tag_ids_by_task(self._session, [task_id]).get(task_id, frozenset())
        return _to_entity(row, tag_ids=tag_ids)

    def update_text(self, user_id: UserId, task_id: TaskId, *, text: str) -> Task:
        row = self._require_row(user_id, task_id)
        row.text = text
        row.text_key = task_text_key(text)
        try:
            return self._persist(row, task_id)
        except IntegrityError as exc:
            raise DuplicateTaskTextError(text) from exc

    def set_positions(self, user_id: UserId, positions: Mapping[TaskId, int]) -> None:
        """Atomically rewrite several of `user_id`'s Tasks' positions (T11 reorder)."""
        rows = self._session.exec(
            select(tables.Task).where(
                tables.Task.user_id == user_id, tables.Task.id.in_(list(positions))
            )
        ).all()
        for row in rows:
            row.position = positions[TaskId(require_id(row.id))]
            self._session.add(row)
        self._session.commit()

    def archive(self, user_id: UserId, task_id: TaskId, *, archived_at: datetime) -> Task:
        row = self._require_row(user_id, task_id)
        row.archived_at = archived_at
        return self._persist(row, task_id)

    def unarchive(self, user_id: UserId, task_id: TaskId, *, position: int) -> Task:
        row = self._require_row(user_id, task_id)
        row.archived_at = None
        row.position = position
        return self._persist(row, task_id)

    def delete(self, user_id: UserId, task_id: TaskId) -> None:
        row = self._get_row(user_id, task_id)
        if row is not None:
            self._session.delete(row)
            self._session.commit()

    def has_pomodoro(self, user_id: UserId, task_id: TaskId) -> bool:
        row = self._session.exec(
            select(tables.Pomodoro.id).where(
                tables.Pomodoro.task_id == task_id, tables.Pomodoro.user_id == user_id
            )
        ).first()
        return row is not None

    def task_ids_with_pomodoros(self, user_id: UserId) -> frozenset[TaskId]:
        rows = self._session.exec(
            select(tables.Pomodoro.task_id).where(tables.Pomodoro.user_id == user_id)
        ).all()
        return frozenset(TaskId(task_id) for task_id in rows)

    def _get_row(self, user_id: UserId, task_id: TaskId) -> tables.Task | None:
        return self._session.exec(
            select(tables.Task).where(tables.Task.id == task_id, tables.Task.user_id == user_id)
        ).first()

    def _require_row(self, user_id: UserId, task_id: TaskId) -> tables.Task:
        row = self._get_row(user_id, task_id)
        if row is None:
            raise RuntimeError(f"Task {task_id} does not exist for user {user_id}.")
        return row

    def _persist(self, row: tables.Task, task_id: TaskId) -> Task:
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        self._session.refresh(row)
        tag_ids = _tag_ids_by_task(self._session, [task_id]).get(task_id, frozenset())
        return _to_entity(row, tag_ids=tag_ids)
