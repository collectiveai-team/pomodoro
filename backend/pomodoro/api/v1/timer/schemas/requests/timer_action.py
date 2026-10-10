"""CES-4 · shared inbound payload for phase-guarded Timer actions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pomodoro.core.timer import TimerPhase


class TimerActionRequest(BaseModel):
    """Name the phase the caller observed before submitting a Timer action."""

    model_config = ConfigDict(extra="forbid")

    expected_phase: TimerPhase
