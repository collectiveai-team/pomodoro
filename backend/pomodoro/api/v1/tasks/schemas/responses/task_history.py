"""CES-4 · outbound payload for one Task's History."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class TaskHistoryDayResponse(BaseModel):
    """One local day of a Task's History."""

    model_config = ConfigDict(extra="forbid")

    day: date
    completed_count: int
    dedicated_seconds: int


class TaskHistoryResponse(BaseModel):
    """A Task's whole History: totals, first/last worked day and per-day rows, newest first."""

    model_config = ConfigDict(extra="forbid")

    completed_count: int
    dedicated_seconds: int
    first_day: date | None
    last_day: date | None
    active_days: int
    days: list[TaskHistoryDayResponse]
