"""The `task_tags` join table (ADR-0002 schema): a Task's Tag assignments."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TaskTagTable(SQLModel, table=True):
    """Composite-PK join row linking a Task to a Tag; `ON DELETE CASCADE` on both sides."""

    __tablename__ = "task_tags"  # pyrefly: ignore[bad-override]
    __table_args__ = (sa.Index("ix_task_tags_tag_id", "tag_id"),)

    task_id: UUID = Field(foreign_key="task.id", primary_key=True, ondelete="CASCADE")
    tag_id: UUID = Field(foreign_key="tag.id", primary_key=True, ondelete="CASCADE")
