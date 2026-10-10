"""Framework-free per-day, per-Task aggregation rule for History (ADR-0002)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pomodoro.core.timer import PomodoroStatus

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date

    from pomodoro.core.tasks import TaskId
    from pomodoro.core.timer import Pomodoro


@dataclass(frozen=True, slots=True)
class TaskDayAggregate:
    """One Task's completed-Pomodoro count and dedicated time on one local day."""

    task_id: TaskId
    completed_count: int
    dedicated_seconds: int


@dataclass(frozen=True, slots=True)
class DayAggregate:
    """A local day's total completed-Pomodoro count plus its per-Task breakdown."""

    day: date
    completed_count: int
    tasks: tuple[TaskDayAggregate, ...]


@dataclass(slots=True)
class _DayTaskTotals:
    """Mutable running totals for one (day, Task) bucket while aggregating."""

    completed_count: int = field(default=0)
    dedicated_seconds: int = field(default=0)


def aggregate_pomodoros_by_day(
    pomodoros: Iterable[Pomodoro], *, time_zone: str
) -> tuple[DayAggregate, ...]:
    """Bucket recorded Pomodoros into local days and Tasks for History (ADR-0002).

    Completed Pomodoros feed the heatmap and each Task's completed count; completed and
    interrupted_logged Pomodoros both contribute dedicated time. A Pomodoro crossing local
    midnight counts entirely on the day its `ended_at` falls in `time_zone`, computed via
    `zoneinfo` only so the rule stays portable across SQLite and PostgreSQL.
    """
    zone = ZoneInfo(time_zone)
    buckets: dict[date, dict[TaskId, _DayTaskTotals]] = {}
    for pomodoro in pomodoros:
        local_day = pomodoro.ended_at.astimezone(zone).date()
        totals = buckets.setdefault(local_day, {}).setdefault(pomodoro.task_id, _DayTaskTotals())
        totals.dedicated_seconds += pomodoro.duration_seconds
        if pomodoro.status is PomodoroStatus.COMPLETED:
            totals.completed_count += 1

    return tuple(_build_day_aggregate(day, tasks) for day, tasks in sorted(buckets.items()))


def _build_day_aggregate(day: date, tasks: dict[TaskId, _DayTaskTotals]) -> DayAggregate:
    task_aggregates = tuple(
        TaskDayAggregate(
            task_id=task_id,
            completed_count=totals.completed_count,
            dedicated_seconds=totals.dedicated_seconds,
        )
        for task_id, totals in sorted(tasks.items(), key=lambda item: str(item[0]))
    )
    completed_count = sum(task.completed_count for task in task_aggregates)
    return DayAggregate(day=day, completed_count=completed_count, tasks=task_aggregates)
