"""SQLModel-backed Tag persistence, implementing the full `TagRepository` Protocol.

`list`/`get_or_create_by_name` were added as a shared prerequisite for T9
(Tasks API: assigning Tags to a Task by name needs to resolve a name to a
`TagId`, creating it if absent). `rename`/`delete` are T11's (Tags API).
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
    """`TagRepository` Protocol implementation backed by a SQLModel engine."""

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

    def rename(self, user_id: UserId, tag_id: TagId, new_name: str) -> Tag:
        stripped = new_name.strip()
        with session_scope(self._engine) as session:
            row = session.get(tables.Tag, tag_id)
            if row is None or row.user_id != user_id:
                raise LookupError(f"Tag {tag_id} does not exist")
            row.name = stripped
            row.name_key = normalize_key(stripped)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_entity(row)

    def delete(self, user_id: UserId, tag_id: TagId) -> None:
        with session_scope(self._engine) as session:
            row = session.get(tables.Tag, tag_id)
            if row is not None and row.user_id == user_id:
                session.delete(row)
                session.commit()
