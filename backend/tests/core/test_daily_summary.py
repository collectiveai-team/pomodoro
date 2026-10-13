"""Unit tests for the pomodoros-until-long-break count in the daily summary."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pomodoro.core.daily_summary import summarize_day
from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import Pomodoro, PomodoroStatus, TimerPhase

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _completed(count: int) -> list[Pomodoro]:
    return [
        Pomodoro(
            task_id=TaskId(uuid4()),
            started_at=NOW,
            ended_at=NOW,
            duration_seconds=25 * 60,
            status=PomodoroStatus.COMPLETED,
        )
        for _ in range(count)
    ]


def _until_long_break(completed: int, phase: TimerPhase) -> int:
    summary = summarize_day(pomodoros=_completed(completed), now=NOW, time_zone="UTC", phase=phase)
    return summary.pomodoros_until_long_break


@pytest.mark.parametrize(("completed", "expected"), [(0, 5), (1, 4), (4, 1), (5, 5), (6, 4)])
def test_outside_ready_for_next_the_count_runs_five_down_to_one(
    completed: int, expected: int
) -> None:
    assert _until_long_break(completed, TimerPhase.IDLE) == expected


@pytest.mark.parametrize(("completed", "expected"), [(1, 4), (5, 0), (10, 0)])
def test_ready_for_next_reaches_zero_right_after_a_fifth_pomodoro(
    completed: int, expected: int
) -> None:
    assert _until_long_break(completed, TimerPhase.READY_FOR_NEXT) == expected
