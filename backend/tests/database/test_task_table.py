"""Unit tests proving the `task` table's partial unique index (CES-18, ADR-0002)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from pomodoro.database.models.task import TaskTable
from pomodoro.database.models.user import UserTable
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

if TYPE_CHECKING:
    from collections.abc import Iterator
    from uuid import UUID

pytestmark = pytest.mark.unit


@pytest.fixture
def session() -> Iterator[Session]:
    engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def _make_user(session: Session) -> UUID:
    user = UserTable(
        id=uuid4(),
        email="owner@example.com",
        email_key="owner@example.com",
        password_hash="hash",
        time_zone="UTC",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user.id


def _add_task(
    session: Session, user_id: UUID, text_key: str, position: int, *, archived: bool = False
) -> None:
    session.add(
        TaskTable(
            user_id=user_id,
            text="Write report",
            text_key=text_key,
            position=position,
            created_at=datetime.now(UTC),
            archived_at=datetime.now(UTC) if archived else None,
        )
    )
    session.commit()


def test_two_active_tasks_with_the_same_text_key_are_rejected(session: Session) -> None:
    user_id = _make_user(session)
    _add_task(session, user_id, "write report", 0)

    with pytest.raises(IntegrityError):
        _add_task(session, user_id, "write report", -1)
    session.rollback()


def test_an_archived_task_does_not_block_an_active_task_with_the_same_text_key(
    session: Session,
) -> None:
    user_id = _make_user(session)
    _add_task(session, user_id, "write report", 0, archived=True)

    _add_task(session, user_id, "write report", -1)  # must not raise


def test_two_different_users_may_share_the_same_text_key(session: Session) -> None:
    first_user_id = _make_user(session)
    session.add(
        UserTable(
            id=uuid4(),
            email="other@example.com",
            email_key="other@example.com",
            password_hash="hash",
            time_zone="UTC",
            created_at=datetime.now(UTC),
        )
    )
    session.commit()
    second_user = session.exec(
        select(UserTable).where(UserTable.email_key == "other@example.com")
    ).one()

    _add_task(session, first_user_id, "write report", 0)
    _add_task(session, second_user.id, "write report", 0)  # must not raise
