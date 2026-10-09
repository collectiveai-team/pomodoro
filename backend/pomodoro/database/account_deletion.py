"""Cascading hard-delete of a User and every row that depends on it (CES-18, T9).

Explicit per-table order, not a bare `session.delete(user_row)` relying on the
database's own `ON DELETE` actions: `pomodoro.task_id` and `timer.task_id` are
RESTRICT (a Task with a Pomodoro, or one the Timer currently points at, can
never be deleted - see `database.tables`), so every Pomodoro and the User's
Timer row must be gone before any Task is. Deleting the User's Tags here too
(rather than letting a Task delete carry them via `task_tags` cascade) clears
the catalog even for a User who never tagged a Task.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlmodel import select

from pomodoro.database import tables

if TYPE_CHECKING:
    from sqlmodel import Session, SQLModel

    from pomodoro.core.entities import UserId


def delete_user_account(session: Session, user_id: UserId) -> None:
    """Permanently delete `user_id` and every row depending on it, then commit."""
    _delete_where(session, tables.AuthSession, tables.AuthSession.user_id == user_id)
    _delete_where(session, tables.Timer, tables.Timer.user_id == user_id)
    _delete_where(session, tables.Pomodoro, tables.Pomodoro.user_id == user_id)
    _delete_where(session, tables.Tag, tables.Tag.user_id == user_id)
    _delete_where(session, tables.Task, tables.Task.user_id == user_id)
    user_row = session.get(tables.User, user_id)
    if user_row is not None:
        session.delete(user_row)
    session.commit()


def _delete_where(session: Session, table: type[SQLModel], condition: Any) -> None:
    for row in session.exec(select(table).where(condition)).all():
        session.delete(row)
