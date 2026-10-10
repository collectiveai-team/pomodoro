"""History use cases: month summary and day detail orchestration (T18)."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from pomodoro.core.history import (
    aggregate_pomodoros_by_day,
    local_day_utc_range,
    local_month_utc_range,
)
from pomodoro.core.task_filtering import filter_tasks

if TYPE_CHECKING:
    from collections.abc import Collection

    from pomodoro.core.history import DayAggregate
    from pomodoro.core.task_filtering import TaskTagFilter
    from pomodoro.core.tasks import Task, TaskRepository
    from pomodoro.core.timer import PomodoroRepository
    from pomodoro.core.users import User


@dataclass(frozen=True, slots=True)
class MonthDaySummary:
    """One local day's completed-Pomodoro count."""

    day: date
    completed_count: int


@dataclass(frozen=True, slots=True)
class MonthSummary:
    """Every day of a local calendar month, for the caller's heatmap."""

    year: int
    month: int
    days: tuple[MonthDaySummary, ...]


@dataclass(frozen=True, slots=True)
class DayTaskSummary:
    """One Task worked on a local day, with its completed count and dedicated time."""

    task: Task
    completed_count: int
    dedicated_seconds: int


@dataclass(frozen=True, slots=True)
class DayDetail:
    """A local day's filtered per-Task breakdown."""

    day: date
    completed_count: int
    tasks: tuple[DayTaskSummary, ...]


def month_summary(
    *, user: User, year: int, month: int, pomodoro_repository: PomodoroRepository
) -> MonthSummary:
    """Return every day's completed-Pomodoro count for `year`/`month`, in the caller's zone."""
    start_utc, end_utc = local_month_utc_range(year, month, time_zone=user.time_zone)
    pomodoros = pomodoro_repository.list_for_user_in_range(user.id, start_utc, end_utc)
    day_aggregates = aggregate_pomodoros_by_day(pomodoros, time_zone=user.time_zone)
    counts_by_day = {aggregate.day: aggregate.completed_count for aggregate in day_aggregates}

    days_in_month = monthrange(year, month)[1]
    days = tuple(
        _month_day_summary(year, month, day_of_month, counts_by_day)
        for day_of_month in range(1, days_in_month + 1)
    )
    return MonthSummary(year=year, month=month, days=days)


def _month_day_summary(
    year: int, month: int, day_of_month: int, counts_by_day: dict[date, int]
) -> MonthDaySummary:
    day = date(year, month, day_of_month)
    return MonthDaySummary(day=day, completed_count=counts_by_day.get(day, 0))


def day_detail(
    *,
    user: User,
    day: date,
    name_query: str | None,
    selected_tags: Collection[TaskTagFilter],
    pomodoro_repository: PomodoroRepository,
    task_repository: TaskRepository,
) -> DayDetail:
    """Return the caller's per-Task completed count and dedicated time for `day`, filtered."""
    start_utc, end_utc = local_day_utc_range(day, time_zone=user.time_zone)
    pomodoros = pomodoro_repository.list_for_user_in_range(user.id, start_utc, end_utc)
    day_aggregates = aggregate_pomodoros_by_day(pomodoros, time_zone=user.time_zone)
    aggregate = _find_day_aggregate(day_aggregates, day)
    if aggregate is None:
        return DayDetail(day=day, completed_count=0, tasks=())

    tasks_by_id = {
        task_aggregate.task_id: task
        for task_aggregate in aggregate.tasks
        if (task := task_repository.get_by_id(user.id, task_aggregate.task_id)) is not None
    }
    filtered_task_ids = {
        task.id for task in filter_tasks(tasks_by_id.values(), name_query, selected_tags)
    }
    summaries = tuple(
        DayTaskSummary(
            task=tasks_by_id[task_aggregate.task_id],
            completed_count=task_aggregate.completed_count,
            dedicated_seconds=task_aggregate.dedicated_seconds,
        )
        for task_aggregate in aggregate.tasks
        if task_aggregate.task_id in filtered_task_ids
    )
    completed_count = sum(summary.completed_count for summary in summaries)
    return DayDetail(day=day, completed_count=completed_count, tasks=summaries)


def _find_day_aggregate(day_aggregates: tuple[DayAggregate, ...], day: date) -> DayAggregate | None:
    for aggregate in day_aggregates:
        if aggregate.day == day:
            return aggregate
    return None
