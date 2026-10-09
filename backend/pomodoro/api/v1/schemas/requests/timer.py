"""Inbound payloads for `api.v1.routers.timer` (CES-4, T13)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StartTimerRequest(BaseModel):
    """POST /api/v1/timer/start payload."""

    model_config = ConfigDict(extra="forbid")

    task_id: int
