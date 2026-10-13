"""CES-4 · inbound payload for POST /api/v1/timer/start."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from pomodoro.core.timer import TimerPhase


class StartTimerRequest(BaseModel):
    """Start a Pomodoro from the Idle or ReadyForNext phase the client last saw."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    expected_phase: TimerPhase
