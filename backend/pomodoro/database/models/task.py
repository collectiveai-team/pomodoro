"""The `task` table (ADR-0002 schema): Active/Archived Tasks, unique per User while Active."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

_ACTIVE_TEXT_KEY_WHERE = sa.text("archived_at IS NULL")


class TaskTable(SQLModel, table=True):
    """Persistence row for a `Task`: adds `text_key`, absent from the core entity.

    The partial unique index enforces text uniqueness only among a User's Active Tasks
    (`archived_at IS NULL`), so an Archived Task never competes with an Active one.
    """

    __tablename__ = "task"  # pyrefly: ignore[bad-override]
    __table_args__ = (
        sa.Index(
            "ix_task_user_id_text_key_active",
            "user_id",
            "text_key",
            unique=True,
            sqlite_where=_ACTIVE_TEXT_KEY_WHERE,
            postgresql_where=_ACTIVE_TEXT_KEY_WHERE,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    text: str
    text_key: str
    position: int
    created_at: datetime
    archived_at: datetime | None = Field(default=None)
