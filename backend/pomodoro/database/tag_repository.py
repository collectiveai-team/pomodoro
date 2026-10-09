"""SQLModel-backed `core.repositories.TagRepository` (CES-18, T12).

Mirrors `database.task_repository.SqlTaskRepository` (T10): the only place a
`tables.Tag` row is mapped to a `core.entities.Tag` dataclass, and every method
takes the owning `UserId` explicitly and filters by it in the query itself, so
cross-User leakage is impossible by construction. Renaming raises
`TagRenameCollisionError` on a `name_key` collision (the `uq_tag_user_id_name_key`
unique constraint, T2); deleting relies on `task_tags`'s `ON DELETE CASCADE` FKs
rather than an application-level cleanup step, so no dangling association can
ever be left behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from pomodoro.core.entities import Tag, TagId, UserId
from pomodoro.core.errors import TagRenameCollisionError
from pomodoro.core.normalization import tag_name_key
from pomodoro.database import tables
from pomodoro.database.rows import require_id

if TYPE_CHECKING:
    from sqlmodel import Session


def _to_entity(row: tables.Tag) -> Tag:
    return Tag(id=TagId(require_id(row.id)), user_id=UserId(row.user_id), name=row.name)


@dataclass
class SqlTagRepository:
    """`core.repositories.TagRepository` implementation over a SQLModel `Session`."""

    _session: Session

    def list_for_user(self, user_id: UserId) -> list[Tag]:
        rows = self._session.exec(select(tables.Tag).where(tables.Tag.user_id == user_id)).all()
        return [_to_entity(row) for row in rows]

    def get(self, user_id: UserId, tag_id: TagId) -> Tag | None:
        row = self._get_row(user_id, tag_id)
        return _to_entity(row) if row is not None else None

    def update_name(self, user_id: UserId, tag_id: TagId, *, name: str) -> Tag:
        row = self._require_row(user_id, tag_id)
        row.name = name
        row.name_key = tag_name_key(name)
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise TagRenameCollisionError(name) from exc
        self._session.refresh(row)
        return _to_entity(row)

    def delete(self, user_id: UserId, tag_id: TagId) -> None:
        row = self._get_row(user_id, tag_id)
        if row is not None:
            self._session.delete(row)
            self._session.commit()

    def _get_row(self, user_id: UserId, tag_id: TagId) -> tables.Tag | None:
        return self._session.exec(
            select(tables.Tag).where(tables.Tag.id == tag_id, tables.Tag.user_id == user_id)
        ).first()

    def _require_row(self, user_id: UserId, tag_id: TagId) -> tables.Tag:
        row = self._get_row(user_id, tag_id)
        if row is None:
            raise RuntimeError(f"Tag {tag_id} does not exist for user {user_id}.")
        return row
