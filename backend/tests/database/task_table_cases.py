"""Shared `user`/`task` row helpers and assertions (ADR-0002).

Reused by the SQLite unit tests (`test_task_table.py`) and the PostgreSQL integration tests
(`tests/integration/test_postgres_constraints.py`, T19), which prove the same partial-unique-index
rule on both engines: a single shared definition, never two copies of the same assertion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pomodoro.database.models.task import TaskTable
from pomodoro.database.models.user import UserTable
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel import Session


def make_user(session: Session, *, email: str = "owner@example.com") -> UUID:
    """Insert and commit a minimal `user` row, returning its id."""
    user = UserTable(
        id=uuid4(),
        email=email,
        email_key=email,
        password_hash="hash",
        time_zone="UTC",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user.id


def add_task(
    session: Session, user_id: UUID, text_key: str, position: int, *, archived: bool = False
) -> UUID:
    """Insert and commit a minimal `task` row, returning its id."""
    task = TaskTable(
        user_id=user_id,
        text="Write report",
        text_key=text_key,
        position=position,
        created_at=datetime.now(UTC),
        archived_at=datetime.now(UTC) if archived else None,
    )
    session.add(task)
    session.commit()
    return task.id


def assert_two_active_tasks_with_the_same_text_key_are_rejected(session: Session) -> None:
    """Assert the partial unique index rejects a second Active Task sharing a `text_key`."""
    user_id = make_user(session)
    add_task(session, user_id, "write report", 0)

    with pytest.raises(IntegrityError):
        add_task(session, user_id, "write report", -1)
    session.rollback()


def assert_an_archived_task_does_not_block_an_active_task_with_the_same_text_key(
    session: Session,
) -> None:
    """Assert an Archived Task never competes with an Active Task for the same `text_key`."""
    user_id = make_user(session)
    add_task(session, user_id, "write report", 0, archived=True)

    add_task(session, user_id, "write report", -1)  # must not raise
