"""Unit tests for the pure History day-aggregation rule (ADR-0002)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pomodoro.core.history import aggregate_pomodoros_by_day
from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import Pomodoro, PomodoroStatus

pytestmark = pytest.mark.unit

TASK_A = TaskId(UUID(int=1))
TASK_B = TaskId(UUID(int=2))


def _pomodoro(
    task_id: TaskId,
    ended_at: datetime,
    *,
    duration_seconds: int = 25 * 60,
    status: PomodoroStatus = PomodoroStatus.COMPLETED,
) -> Pomodoro:
    return Pomodoro(
        task_id=task_id,
        started_at=ended_at - timedelta(seconds=duration_seconds),
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        status=status,
    )


def test_aggregates_completed_count_and_dedicated_time_per_day_and_task() -> None:
    completed = _pomodoro(TASK_A, datetime(2026, 3, 1, 10, 0, tzinfo=UTC))
    interrupted = _pomodoro(
        TASK_A,
        datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
        duration_seconds=10 * 60,
        status=PomodoroStatus.INTERRUPTED_LOGGED,
    )

    days = aggregate_pomodoros_by_day([completed, interrupted], time_zone="UTC")

    assert len(days) == 1
    day = days[0]
    assert day.day == datetime(2026, 3, 1, tzinfo=UTC).date()
    assert day.completed_count == 1
    assert len(day.tasks) == 1
    task_totals = day.tasks[0]
    assert task_totals.task_id == TASK_A
    assert task_totals.completed_count == 1
    assert task_totals.dedicated_seconds == 25 * 60 + 10 * 60


def test_pomodoro_crossing_local_midnight_counts_entirely_on_the_local_day() -> None:
    # 23:30 UTC on 2026-03-01 is 00:30 on 2026-03-02 in UTC+1.
    ended_at_utc = datetime(2026, 3, 1, 23, 30, tzinfo=UTC)
    pomodoro = _pomodoro(TASK_A, ended_at_utc)

    days = aggregate_pomodoros_by_day([pomodoro], time_zone="Europe/Paris")

    assert len(days) == 1
    assert days[0].day == datetime(2026, 3, 2, tzinfo=UTC).date()
    assert days[0].completed_count == 1


def test_two_users_in_different_time_zones_aggregate_independently() -> None:
    shared_instant = datetime(2026, 3, 1, 23, 30, tzinfo=UTC)
    user_one_pomodoros = [_pomodoro(TASK_A, shared_instant)]
    user_two_pomodoros = [_pomodoro(TASK_B, shared_instant)]

    user_one_days = aggregate_pomodoros_by_day(user_one_pomodoros, time_zone="Europe/Paris")
    user_two_days = aggregate_pomodoros_by_day(user_two_pomodoros, time_zone="America/New_York")

    assert user_one_days[0].day == datetime(2026, 3, 2, tzinfo=UTC).date()
    assert user_two_days[0].day == datetime(2026, 3, 1, tzinfo=UTC).date()
    assert user_one_days[0].tasks[0].task_id == TASK_A
    assert user_two_days[0].tasks[0].task_id == TASK_B


def test_archived_tasks_still_appear_for_days_they_were_worked() -> None:
    # The rule only ever sees Pomodoros, never Task.archived_at, so a Task's archive
    # status cannot exclude it: every task_id with a recorded Pomodoro on a day appears.
    archived_task_pomodoro = _pomodoro(TASK_A, datetime(2026, 3, 1, 9, 0, tzinfo=UTC))
    active_task_pomodoro = _pomodoro(TASK_B, datetime(2026, 3, 1, 9, 0, tzinfo=UTC))

    days = aggregate_pomodoros_by_day(
        [archived_task_pomodoro, active_task_pomodoro], time_zone="UTC"
    )

    task_ids = {task.task_id for task in days[0].tasks}
    assert task_ids == {TASK_A, TASK_B}


def test_days_with_no_pomodoros_produce_no_aggregate_entry() -> None:
    assert aggregate_pomodoros_by_day([], time_zone="UTC") == ()
