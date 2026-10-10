"""CES-4 · outbound payload for the persisted Timer lifecycle."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pomodoro.core.timer import BreakKind, TimerPhase


class InProgressTaskResponse(BaseModel):
    """The Task currently held by a non-Idle Timer, without Task-list-only fields."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str


class TimerResponse(BaseModel):
    """The settled Timer plus all data needed for a clock-skew-corrected countdown."""

    model_config = ConfigDict(extra="forbid")

    phase: TimerPhase
    task: InProgressTaskResponse | None
    break_kind: BreakKind | None
    phase_started_at: datetime | None
    accumulated_active_seconds: int
    running_since: datetime | None
    server_now: datetime
    remaining_seconds: int | None
