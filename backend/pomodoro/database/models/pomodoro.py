"""The `pomodoro` table (ADR-0002 schema): minimal prerequisite for T7's delete-block rule.

Only the raw table lands here. The `Pomodoro` core entity, `PomodoroRepository` Protocol, and
Timer wiring are T11's scope; until then, `TaskRepository.task_ids_with_pomodoros` is this
table's only consumer, answering "has this Task ever had a Pomodoro recorded" for Task deletion.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class PomodoroTable(SQLModel, table=True):
    """Persistence row for a completed or interrupted-logged Pomodoro."""

    __tablename__ = "pomodoro"  # pyrefly: ignore[bad-override]
    __table_args__ = (
        sa.CheckConstraint("duration_seconds > 0", name="ck_pomodoro_duration_seconds_positive"),
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
