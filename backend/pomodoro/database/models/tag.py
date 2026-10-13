"""The `tag` table (ADR-0002 schema): a User-scoped label, unique per User by `name_key`."""

from __future__ import annotations

from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TagTable(SQLModel, table=True):
    """Persistence row for a `Tag`; `name_key` mirrors the same field on the core entity."""

    __tablename__ = "tag"  # pyrefly: ignore[bad-override]
    __table_args__ = (sa.Index("ix_tag_user_id_name_key", "user_id", "name_key", unique=True),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    name: str
    name_key: str
