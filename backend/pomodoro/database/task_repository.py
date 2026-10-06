"""SQLModel-backed `TaskRepository` Protocol implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from pomodoro.core.entities import TagId, Task, TaskId, UserId
from pomodoro.core.errors import DuplicateActiveTaskTextError
from pomodoro.core.normalization import normalize_key
from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from sqlmodel import Session


def _require_row_id(row: tables.Task) -> int:
    if row.id is None:
        raise AssertionError
    return row.id


def _tag_ids_for_task(session: Session, task_id: int) -> tuple[TagId, ...]:
    rows = session.exec(
        select(tables.TaskTag.tag_id).where(tables.TaskTag.task_id == task_id)
    ).all()
    return tuple(TagId(tag_id) for tag_id in rows)


def _to_entity(row: tables.Task, tag_ids: tuple[TagId, ...]) -> Task:
    if row.id is None:
        raise AssertionError
    return Task(
        id=TaskId(row.id),
        user_id=UserId(row.user_id),
        text=row.text,
        position=row.position,
        tag_ids=tag_ids,
        created_at=row.created_at,
        archived_at=row.archived_at,
    )


def _replace_tag_links(session: Session, task_id: int, tag_ids: tuple[TagId, ...]) -> None:
    existing = session.exec(select(tables.TaskTag).where(tables.TaskTag.task_id == task_id)).all()
    for link in existing:
        session.delete(link)
    for tag_id in tag_ids:
        session.add(tables.TaskTag(task_id=task_id, tag_id=tag_id))


class SQLTaskRepository:
    """`TaskRepository` Protocol implementation backed by a SQLModel engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_active(self, user_id: UserId) -> list[Task]:
        with session_scope(self._engine) as session:
            rows = session.exec(
                select(tables.Task).where(
                    tables.Task.user_id == user_id, col(tables.Task.archived_at).is_(None)
                )
            ).all()
            return [
                _to_entity(row, _tag_ids_for_task(session, _require_row_id(row))) for row in rows
            ]

    def list_archived(self, user_id: UserId) -> list[Task]:
        with session_scope(self._engine) as session:
            rows = session.exec(
                select(tables.Task).where(
                    tables.Task.user_id == user_id, col(tables.Task.archived_at).is_not(None)
                )
            ).all()
            return [
                _to_entity(row, _tag_ids_for_task(session, _require_row_id(row))) for row in rows
            ]

    def get(self, user_id: UserId, task_id: TaskId) -> Task | None:
        with session_scope(self._engine) as session:
            row = session.get(tables.Task, task_id)
            if row is None or row.user_id != user_id:
                return None
            return _to_entity(row, _tag_ids_for_task(session, _require_row_id(row)))

    def add(self, task: Task) -> Task:
        with session_scope(self._engine) as session:
            row = tables.Task(
                user_id=task.user_id,
                text=task.text,
                text_key=normalize_key(task.text),
                position=task.position,
                created_at=task.created_at,
                archived_at=task.archived_at,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as error:
                # Two concurrent creates can both pass the caller's
                # `list_active`-based uniqueness pre-check before either
                # inserts; the partial unique index on (user_id, text_key)
                # while Active is the last line of defence, and must surface
                # as the same domain error the pre-check raises rather than
                # an unhandled database error.
                session.rollback()
                raise DuplicateActiveTaskTextError from error
            session.refresh(row)
            _replace_tag_links(session, _require_row_id(row), task.tag_ids)
            session.commit()
            return _to_entity(row, task.tag_ids)

    def update(self, task: Task) -> Task:
        with session_scope(self._engine) as session:
            row = session.get(tables.Task, task.id)
            if row is None:
                raise LookupError(f"Task {task.id} does not exist")
            row.text = task.text
            row.text_key = normalize_key(task.text)
            row.position = task.position
            row.archived_at = task.archived_at
            session.add(row)
            _replace_tag_links(session, task.id, task.tag_ids)
            session.commit()
            session.refresh(row)
            return _to_entity(row, task.tag_ids)

    def delete(self, user_id: UserId, task_id: TaskId) -> None:
        with session_scope(self._engine) as session:
            row = session.get(tables.Task, task_id)
            if row is not None and row.user_id == user_id:
                session.delete(row)
                session.commit()
