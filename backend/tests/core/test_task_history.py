"""Unit tests for the pure per-Task History rule."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from pomodoro.core.history import TaskHistoryDay, build_task_history
from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import Pomodoro, PomodoroStatus

pytestmark = pytest.mark.unit

TASK = TaskId(UUID(int=1))


def _pomodoro(
    ended_at: datetime,
    *,
    duration_seconds: int = 25 * 60,
    status: PomodoroStatus = PomodoroStatus.COMPLETED,
) -> Pomodoro:
    return Pomodoro(
        task_id=TASK,
        started_at=ended_at - timedelta(seconds=duration_seconds),
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        status=status,
    )


def test_task_without_pomodoros_has_zero_totals_and_no_days() -> None:
    history = build_task_history([], time_zone="UTC")

    assert history.completed_count == 0
    assert history.dedicated_seconds == 0
    assert history.first_day is None
    assert history.last_day is None
    assert history.active_days == 0
    assert history.days == ()


def test_totals_range_and_days_are_most_recent_first() -> None:
    history = build_task_history(
        [
            _pomodoro(datetime(2026, 3, 1, 10, 0, tzinfo=UTC)),
            _pomodoro(datetime(2026, 3, 5, 10, 0, tzinfo=UTC)),
            _pomodoro(datetime(2026, 3, 5, 12, 0, tzinfo=UTC)),
        ],
        time_zone="UTC",
    )

    assert history.completed_count == 3
    assert history.dedicated_seconds == 3 * 25 * 60
    assert history.first_day == date(2026, 3, 1)
    assert history.last_day == date(2026, 3, 5)
    assert history.active_days == 2
    assert history.days == (
        TaskHistoryDay(day=date(2026, 3, 5), completed_count=2, dedicated_seconds=2 * 25 * 60),
        TaskHistoryDay(day=date(2026, 3, 1), completed_count=1, dedicated_seconds=25 * 60),
    )


def test_interrupted_logged_adds_time_but_not_count() -> None:
    history = build_task_history(
        [
            _pomodoro(datetime(2026, 3, 1, 10, 0, tzinfo=UTC)),
            _pomodoro(
                datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
                duration_seconds=10 * 60,
                status=PomodoroStatus.INTERRUPTED_LOGGED,
            ),
        ],
        time_zone="UTC",
    )

    assert history.completed_count == 1
    assert history.dedicated_seconds == 35 * 60
    assert history.days == (
        TaskHistoryDay(day=date(2026, 3, 1), completed_count=1, dedicated_seconds=35 * 60),
    )


def test_day_cutoff_uses_the_user_time_zone_near_midnight() -> None:
    # 23:30 UTC on 2026-03-01 is 00:30 on 2026-03-02 in Paris but 18:30 on 03-01 in New York.
    pomodoro = _pomodoro(datetime(2026, 3, 1, 23, 30, tzinfo=UTC))

    paris = build_task_history([pomodoro], time_zone="Europe/Paris")
    new_york = build_task_history([pomodoro], time_zone="America/New_York")

    assert paris.first_day == date(2026, 3, 2)
    assert new_york.first_day == date(2026, 3, 1)
