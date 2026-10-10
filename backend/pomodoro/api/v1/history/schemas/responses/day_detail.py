"""CES-4 · outbound payload for GET /api/v1/history/day."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DayTaskSummaryResponse(BaseModel):
    """One Task's completed-Pomodoro count and dedicated time on a local day."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    text: str
    completed_count: int
    dedicated_seconds: int


class DayDetailResponse(BaseModel):
    """A local day's filtered per-Task breakdown, scoped to the caller."""

    model_config = ConfigDict(extra="forbid")

    day: date
    completed_count: int
    tasks: list[DayTaskSummaryResponse]
