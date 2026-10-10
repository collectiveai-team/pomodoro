"""The `pomodoro` table (ADR-0002 schema)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class PomodoroTable(SQLModel, table=True):
    """Persistence row for a completed or interrupted-logged Pomodoro."""

    __tablename__ = "pomodoro"  # pyrefly: ignore[bad-override]
    __table_args__ = (
        sa.CheckConstraint(
            "duration_seconds >= 0", name="ck_pomodoro_duration_seconds_nonnegative"
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'interrupted_logged')", name="ck_pomodoro_status"
        ),
        sa.CheckConstraint("ended_at >= started_at", name="ck_pomodoro_ended_at_after_started_at"),
        sa.Index("ix_pomodoro_user_id_ended_at", "user_id", "ended_at"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    task_id: UUID = Field(foreign_key="task.id", index=True, ondelete="RESTRICT")
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    status: str
