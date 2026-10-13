"""The `timer` table: one persisted live Timer state for each User (ADR-0003)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel


class TimerTable(SQLModel, table=True):
    """Persistence row for the state required to reconstruct a User's Timer."""

    __tablename__ = "timer"  # pyrefly: ignore[bad-override]

    user_id: UUID = Field(primary_key=True, foreign_key="user.id", ondelete="CASCADE")
    phase: str
    task_id: UUID | None = Field(default=None, foreign_key="task.id", ondelete="RESTRICT")
    break_kind: str | None = Field(default=None)
    phase_started_at: datetime | None = Field(default=None)
    accumulated_active_seconds: int = Field(default=0)
    running_since: datetime | None = Field(default=None)
