"""SQLModel implementation of `TagRepository` (T8)."""

from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session, select

from pomodoro.core.tags import Tag, TagId, TagRepository
from pomodoro.core.users import UserId
from pomodoro.database.models.tag import TagTable
from pomodoro.database.session import get_db_session


class SqlTagRepository:
    """`TagRepository` backed by the `tag` SQLModel table, scoped to a `UserId`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, tag: Tag) -> None:
        """Insert a new `tag` row and commit."""
        self._session.add(
            TagTable(id=tag.id, user_id=tag.user_id, name=tag.name, name_key=tag.name_key)
        )
        self._session.commit()

    def get_by_id(self, user_id: UserId, tag_id: TagId) -> Tag | None:
        """Return the caller's Tag with this id, or None if absent or owned by another User."""
        row = self._session.get(TagTable, tag_id)
        if row is None or row.user_id != user_id:
            return None
        return _to_entity(row)

    def list_all(self, user_id: UserId) -> list[Tag]:
        """Return every Tag in the caller's catalog, including ones carried by no Task."""
        rows = self._session.exec(select(TagTable).where(TagTable.user_id == user_id)).all()
        return [_to_entity(row) for row in rows]

    def update_name(self, user_id: UserId, tag_id: TagId, name: str, name_key: str) -> None:
        """Overwrite a Tag's name and derived key."""
        row = self._session.get(TagTable, tag_id)
        if row is None or row.user_id != user_id:
            return
        row.name = name
        row.name_key = name_key
        self._session.add(row)
        self._session.commit()

    def delete(self, user_id: UserId, tag_id: TagId) -> None:
        """Permanently remove the caller's Tag; `task_tags` rows cascade via the FK."""
        row = self._session.get(TagTable, tag_id)
        if row is None or row.user_id != user_id:
            return
        self._session.delete(row)
        self._session.commit()


def _to_entity(row: TagTable) -> Tag:
    return Tag(id=TagId(row.id), user_id=UserId(row.user_id), name=row.name, name_key=row.name_key)


def get_tag_repository(session: Session = Depends(get_db_session)) -> TagRepository:
    """FastAPI provider: a `TagRepository` backed by the request's DB session."""
    return SqlTagRepository(session)
