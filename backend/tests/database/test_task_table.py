"""Unit tests proving the `task` table's partial unique index (CES-18, ADR-0002)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.engine import build_engine
from pomodoro.database.models.user import UserTable
from sqlmodel import Session, SQLModel, select
from tests.database.task_table_cases import (
    add_task,
    assert_an_archived_task_does_not_block_an_active_task_with_the_same_text_key,
    assert_two_active_tasks_with_the_same_text_key_are_rejected,
    make_user,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit


@pytest.fixture
def session() -> Iterator[Session]:
    engine = build_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def test_two_active_tasks_with_the_same_text_key_are_rejected(session: Session) -> None:
    assert_two_active_tasks_with_the_same_text_key_are_rejected(session)


def test_an_archived_task_does_not_block_an_active_task_with_the_same_text_key(
    session: Session,
) -> None:
    assert_an_archived_task_does_not_block_an_active_task_with_the_same_text_key(session)


def test_two_different_users_may_share_the_same_text_key(session: Session) -> None:
    first_user_id = make_user(session)
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

    add_task(session, first_user_id, "write report", 0)
    add_task(session, second_user.id, "write report", 0)  # must not raise
