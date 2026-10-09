"""Tests for the History aggregation rule in core/ (T16; ADR-0002)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from pomodoro.core.entities import Pomodoro, PomodoroId, PomodoroStatus, TaskId, UserId
from pomodoro.core.history import DayCount, TaskDayDetail, day_detail, monthly_heatmap

pytestmark = pytest.mark.unit

_USER = UserId(1)
_OTHER_USER = UserId(2)
_TASK = TaskId(1)
_OTHER_TASK = TaskId(2)
_BOGOTA = "America/Bogota"  # UTC-05:00, no DST - a non-UTC-offset zone.


def _pomodoro(
    pomodoro_id: int,
    *,
    ended_at: datetime,
    duration_seconds: int = 1500,
    status: PomodoroStatus = PomodoroStatus.COMPLETED,
    task_id: TaskId = _TASK,
    user_id: UserId = _USER,
) -> Pomodoro:
    return Pomodoro(
        id=PomodoroId(pomodoro_id),
        user_id=user_id,
        task_id=task_id,
        started_at=ended_at - timedelta(seconds=duration_seconds),
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        status=status,
    )


class TestMonthlyHeatmap:
    def test_counts_completed_pomodoros_per_local_day(self) -> None:
        pomodoros = [
            _pomodoro(1, ended_at=datetime(2026, 3, 5, 15, 0, tzinfo=UTC)),
            _pomodoro(2, ended_at=datetime(2026, 3, 5, 18, 0, tzinfo=UTC)),
            _pomodoro(3, ended_at=datetime(2026, 3, 6, 15, 0, tzinfo=UTC)),
        ]
        assert monthly_heatmap(pomodoros, time_zone=_BOGOTA) == [
            DayCount(day=date(2026, 3, 5), completed_count=2),
            DayCount(day=date(2026, 3, 6), completed_count=1),
        ]

    def test_excludes_interrupted_logged_runs(self) -> None:
        pomodoros = [
            _pomodoro(
                1,
                ended_at=datetime(2026, 3, 5, 15, 0, tzinfo=UTC),
                status=PomodoroStatus.INTERRUPTED_LOGGED,
            )
        ]
        assert monthly_heatmap(pomodoros, time_zone=_BOGOTA) == []

    def test_a_pomodoro_ending_just_after_local_midnight_counts_on_the_later_day(self) -> None:
        """Spec story 80: crossing local midnight attributes the whole run to the later day."""
        zone = ZoneInfo(_BOGOTA)
        # Started 2026-03-05 23:50 local, ended 2026-03-06 00:10 local - crosses midnight.
        ended_at_local = datetime(2026, 3, 6, 0, 10, tzinfo=zone)
        pomodoro = _pomodoro(1, ended_at=ended_at_local.astimezone(UTC), duration_seconds=1200)

        result = monthly_heatmap([pomodoro], time_zone=_BOGOTA)

        assert result == [DayCount(day=date(2026, 3, 6), completed_count=1)]

    def test_two_users_in_different_time_zones_group_the_same_instant_differently(self) -> None:
        # 2026-03-06T02:30Z is 2026-03-05 21:30 in Bogota (UTC-5) but already
        # 2026-03-06 11:30 in Tokyo (UTC+9) - same UTC window, different local day.
        ended_at = datetime(2026, 3, 6, 2, 30, tzinfo=UTC)
        pomodoro = _pomodoro(1, ended_at=ended_at)

        bogota_result = monthly_heatmap([pomodoro], time_zone=_BOGOTA)
        tokyo_result = monthly_heatmap([pomodoro], time_zone="Asia/Tokyo")

        assert bogota_result == [DayCount(day=date(2026, 3, 5), completed_count=1)]
        assert tokyo_result == [DayCount(day=date(2026, 3, 6), completed_count=1)]


class TestDayDetail:
    def test_sums_completed_and_interrupted_logged_time_per_task(self) -> None:
        day = date(2026, 3, 5)
        pomodoros = [
            _pomodoro(1, ended_at=datetime(2026, 3, 5, 15, 0, tzinfo=UTC), duration_seconds=1500),
            _pomodoro(
                2,
                ended_at=datetime(2026, 3, 5, 18, 0, tzinfo=UTC),
                duration_seconds=600,
                status=PomodoroStatus.INTERRUPTED_LOGGED,
            ),
            _pomodoro(
                3,
                ended_at=datetime(2026, 3, 5, 19, 0, tzinfo=UTC),
                duration_seconds=1500,
                task_id=_OTHER_TASK,
            ),
        ]

        result = day_detail(pomodoros, time_zone=_BOGOTA, day=day)

        assert sorted(result, key=lambda entry: entry.task_id) == [
            TaskDayDetail(task_id=_TASK, completed_count=1, total_seconds=2100),
            TaskDayDetail(task_id=_OTHER_TASK, completed_count=1, total_seconds=1500),
        ]

    def test_excludes_pomodoros_from_other_local_days(self) -> None:
        pomodoros = [_pomodoro(1, ended_at=datetime(2026, 3, 6, 15, 0, tzinfo=UTC))]
        assert day_detail(pomodoros, time_zone=_BOGOTA, day=date(2026, 3, 5)) == []

    def test_a_pomodoro_ending_just_after_local_midnight_belongs_to_the_later_day(self) -> None:
        zone = ZoneInfo(_BOGOTA)
        ended_at_local = datetime(2026, 3, 6, 0, 10, tzinfo=zone)
        pomodoro = _pomodoro(1, ended_at=ended_at_local.astimezone(UTC))

        assert day_detail(pomodoros=[pomodoro], time_zone=_BOGOTA, day=date(2026, 3, 5)) == []
        assert day_detail(pomodoros=[pomodoro], time_zone=_BOGOTA, day=date(2026, 3, 6)) == [
            TaskDayDetail(task_id=_TASK, completed_count=1, total_seconds=1500)
        ]

    def test_two_users_in_different_time_zones_group_the_same_instant_differently(self) -> None:
        ended_at = datetime(2026, 3, 6, 2, 30, tzinfo=UTC)
        pomodoro = _pomodoro(1, ended_at=ended_at, user_id=_OTHER_USER)

        bogota_same_day = day_detail([pomodoro], time_zone=_BOGOTA, day=date(2026, 3, 6))
        tokyo_same_day = day_detail([pomodoro], time_zone="Asia/Tokyo", day=date(2026, 3, 6))

        assert bogota_same_day == []
        assert tokyo_same_day == [
            TaskDayDetail(task_id=_TASK, completed_count=1, total_seconds=1500)
        ]
