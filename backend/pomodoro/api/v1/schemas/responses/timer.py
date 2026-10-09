"""Outbound payloads for `api.v1.routers.timer` (CES-4, T13).

`TimerResponse` is also the body of the 409 a mismatched action gets back
(`entrypoints.app`'s `TimerActionNotAllowedError` handler), carrying the
current (settled) Timer instead of the single generic `ErrorResponse` shape -
so a rejected action still tells the caller exactly what to resync to.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimerResponse(BaseModel):
    """The authenticated User's Timer, settled against the server's clock."""

    model_config = ConfigDict(extra="forbid")

    phase: str
    task_id: int | None
    break_kind: str | None
    phase_started_at: datetime | None
    phase_ended_at: datetime | None
    accumulated_active_seconds: int
    remaining_seconds: int | None
    server_now: datetime


class DaySummaryResponse(BaseModel):
    """GET /api/v1/timer/day-summary payload."""

    model_config = ConfigDict(extra="forbid")

    completed_today: int
    remaining_to_long_break: int
