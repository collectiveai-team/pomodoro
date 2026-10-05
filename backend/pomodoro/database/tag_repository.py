"""SQLModel-backed Tag persistence.

Shared prerequisite for T9 (Tasks API): assigning Tags to a Task by name
requires resolving a name to a `TagId`, creating it if absent. Only the
methods T9 needs (`list`, `get_or_create_by_name`) are implemented here;
`rename`/`delete` -- the rest of `pomodoro.core.repositories.TagRepository` --
are T11's (Tags API) to add.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from pomodoro.core.entities import Tag, TagId, UserId
from pomodoro.core.normalization import normalize_key
from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _to_entity(row: tables.Tag) -> Tag:
    if row.id is None:
        raise AssertionError
    return Tag(id=TagId(row.id), user_id=UserId(row.user_id), name=row.name, name_key=row.name_key)


class SQLTagRepository:
    """Partial `TagRepository` Protocol implementation backed by a SQLModel engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list(self, user_id: UserId) -> list[Tag]:
        with session_scope(self._engine) as session:
            rows = session.exec(select(tables.Tag).where(tables.Tag.user_id == user_id)).all()
            return [_to_entity(row) for row in rows]

    def get_or_create_by_name(self, user_id: UserId, name: str) -> Tag:
        stripped = name.strip()
        key = normalize_key(stripped)
        with session_scope(self._engine) as session:
            row = session.exec(
                select(tables.Tag).where(tables.Tag.user_id == user_id, tables.Tag.name_key == key)
            ).first()
            if row is None:
                row = tables.Tag(user_id=user_id, name=stripped, name_key=key)
                session.add(row)
                session.commit()
                session.refresh(row)
            return _to_entity(row)
