"""Repository tests for Tag persistence of `color` (T2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pomodoro.core.tags import Tag, TagColor, TagId
from pomodoro.core.users import UserId
from pomodoro.database import models  # noqa: F401 — registers every table on SQLModel.metadata
from pomodoro.database.models.user import UserTable
from pomodoro.database.repositories.tag import SqlTagRepository

if TYPE_CHECKING:
    from sqlmodel import Session

pytestmark = pytest.mark.unit


@pytest.fixture
def user_id(session: Session) -> UserId:
    """Persist a User so Tag rows satisfy their foreign key."""
    uid = uuid4()
    session.add(
        UserTable(
            id=uid,
            email="a@example.com",
            email_key="a@example.com",
            password_hash="x",
            time_zone="UTC",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.commit()
    return UserId(uid)


def _tag(user_id: UserId, name: str, color: TagColor) -> Tag:
    return Tag(TagId(uuid4()), user_id, name, name.casefold(), color)


def test_added_tag_is_read_back_with_its_color(session: Session, user_id: UserId) -> None:
    repo = SqlTagRepository(session)
    tag = _tag(user_id, "Urgent", TagColor.VIOLET)

    repo.add(tag)

    assert repo.get_by_id(user_id, tag.id) == tag
    assert [t.color for t in repo.list_all(user_id)] == [TagColor.VIOLET]


def test_rename_keeps_the_stored_color(session: Session, user_id: UserId) -> None:
    repo = SqlTagRepository(session)
    tag = _tag(user_id, "Urgent", TagColor.SKY)
    repo.add(tag)

    repo.update_name(user_id, tag.id, "Later", "later")

    renamed = repo.get_by_id(user_id, tag.id)
    assert renamed is not None
    assert (renamed.name, renamed.color) == ("Later", TagColor.SKY)
