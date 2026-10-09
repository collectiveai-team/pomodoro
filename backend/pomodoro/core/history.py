"""The History aggregation rule (core, T16; ADR-0002).

Each finished Pomodoro belongs wholly to the local calendar day of its
`ended_at`, converted via `zoneinfo` in the User's `time_zone` - never a
dialect-specific SQL function (`strftime`/`AT TIME ZONE`), so the same code
groups identically whether the rows came from SQLite or PostgreSQL. The
per-day/per-Task *count* is of `COMPLETED` Pomodoros only; the *dedicated
time* sums both `COMPLETED` and `INTERRUPTED_LOGGED` durations (issue #12
spec story 79).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pomodoro.core.entities import PomodoroStatus

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from pomodoro.core.entities import Pomodoro, TaskId


def _local_day(pomodoro: Pomodoro, zone: ZoneInfo) -> date:
    return pomodoro.ended_at.astimezone(zone).date()


@dataclass(frozen=True, slots=True)
class DayCount:
    """One calendar day's completed-Pomodoro count, for the monthly heatmap."""

    day: date
    completed_count: int


def monthly_heatmap(pomodoros: Sequence[Pomodoro], *, time_zone: str) -> list[DayCount]:
    """Count `COMPLETED` Pomodoros per local day in `time_zone`.

    `INTERRUPTED_LOGGED` runs never contribute to the heatmap count (issue #12
    spec: "el conteo por día ... es de completados").
    """
    zone = ZoneInfo(time_zone)
    counts: dict[date, int] = {}
    for pomodoro in pomodoros:
        if pomodoro.status is not PomodoroStatus.COMPLETED:
            continue
        day = _local_day(pomodoro, zone)
        counts[day] = counts.get(day, 0) + 1
    return [DayCount(day=day, completed_count=count) for day, count in sorted(counts.items())]


@dataclass(frozen=True, slots=True)
class TaskDayDetail:
    """One Task's contribution to a day's detail strip: completed count + dedicated time."""

    task_id: TaskId
    completed_count: int
    total_seconds: int


def day_detail(pomodoros: Sequence[Pomodoro], *, time_zone: str, day: date) -> list[TaskDayDetail]:
    """Per-Task completed count and dedicated time (both statuses) for `day`.

    `day` is a local calendar date in `time_zone`; each Pomodoro is attributed
    whole to the local day of its `ended_at`, never split across a midnight
    boundary (issue #12 spec story 80).
    """
    zone = ZoneInfo(time_zone)
    completed_counts: dict[TaskId, int] = {}
    total_seconds: dict[TaskId, int] = {}
    for pomodoro in pomodoros:
        if _local_day(pomodoro, zone) != day:
            continue
        total_seconds[pomodoro.task_id] = (
            total_seconds.get(pomodoro.task_id, 0) + pomodoro.duration_seconds
        )
        if pomodoro.status is PomodoroStatus.COMPLETED:
            completed_counts[pomodoro.task_id] = completed_counts.get(pomodoro.task_id, 0) + 1
    return [
        TaskDayDetail(
            task_id=task_id,
            completed_count=completed_counts.get(task_id, 0),
            total_seconds=seconds,
        )
        for task_id, seconds in total_seconds.items()
    ]
