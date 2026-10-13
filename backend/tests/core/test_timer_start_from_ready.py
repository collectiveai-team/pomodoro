"""Unit tests for starting a Pomodoro from ReadyForNext on any Task (ADR-0005)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import (
    BreakKind,
    InvalidTimerTransitionError,
    Timer,
    TimerPhase,
    start,
)

pytestmark = pytest.mark.unit

COMPLETED_TASK_ID = TaskId(UUID(int=1))
OTHER_TASK_ID = TaskId(UUID(int=2))
NOW = datetime(2026, 1, 1, 9, tzinfo=UTC)


def _ready_for_next() -> Timer:
    return Timer(
        phase=TimerPhase.READY_FOR_NEXT,
        task_id=COMPLETED_TASK_ID,
        phase_started_at=NOW.replace(hour=8),
    )


@pytest.mark.parametrize("task_id", [OTHER_TASK_ID, COMPLETED_TASK_ID])
def test_ready_for_next_starts_a_pomodoro_on_the_given_task_without_a_break(
    task_id: TaskId,
) -> None:
    timer = start(_ready_for_next(), task_id=task_id, now=NOW)

    assert timer == Timer(
        phase=TimerPhase.POMODORO_RUNNING,
        task_id=task_id,
        break_kind=None,
        phase_started_at=NOW,
        accumulated_active_seconds=0,
        running_since=NOW,
    )


@pytest.mark.parametrize(
    "phase",
    [
        TimerPhase.POMODORO_RUNNING,
        TimerPhase.POMODORO_PAUSED,
        TimerPhase.ASKING_TO_LOG,
        TimerPhase.BREAK_RUNNING,
        TimerPhase.BREAK_PAUSED,
    ],
)
def test_start_still_rejects_every_other_phase(phase: TimerPhase) -> None:
    timer = Timer(phase=phase, task_id=COMPLETED_TASK_ID, break_kind=BreakKind.SHORT)

    with pytest.raises(InvalidTimerTransitionError):
        start(timer, task_id=OTHER_TASK_ID, now=NOW)
