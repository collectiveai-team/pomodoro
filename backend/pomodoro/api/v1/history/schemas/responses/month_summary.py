"""CES-4 · outbound payload for GET /api/v1/history/month."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class MonthDaySummaryResponse(BaseModel):
    """One local day's completed-Pomodoro count, for the caller's 5-level heatmap."""

    model_config = ConfigDict(extra="forbid")

    day: date
    completed_count: int


class MonthSummaryResponse(BaseModel):
    """Every day of a local calendar month, scoped to the caller."""

    model_config = ConfigDict(extra="forbid")

    year: int
    month: int
    days: list[MonthDaySummaryResponse]
