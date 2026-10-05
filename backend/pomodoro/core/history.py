"""The History aggregation rule: monthly heatmap counts and day-level Task detail.

Pure core: no FastAPI/SQLModel/Pydantic imports. A Pomodoro belongs entirely
to the local calendar day of its `ended_at`, per the User's `time_zone`,
computed with `zoneinfo` rather than any engine-specific SQL (story 80).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pomodoro.core.entities import PomodoroStatus
from pomodoro.core.filtering import filter_tasks

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from pomodoro.core.entities import Pomodoro, TagId, Task, TaskId

_DEDICATED_STATUSES = (PomodoroStatus.COMPLETED, PomodoroStatus.INTERRUPTED_LOGGED)


def month_bounds_utc(year: int, month: int, time_zone: str) -> tuple[datetime, datetime]:
    """Return the `[start, end)` UTC instants covering a local calendar month."""
    zone = ZoneInfo(time_zone)
    start_local = datetime(year, month, 1, tzinfo=zone)
    end_local = (
        datetime(year + 1, 1, 1, tzinfo=zone)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=zone)
    )
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


@dataclass(frozen=True)
class DayCount:
    """A single local day's count of completed Pomodoros, for the heatmap."""

    day: date
    completed_count: int


def monthly_heatmap(
    pomodoros: Sequence[Pomodoro], year: int, month: int, time_zone: str
) -> list[DayCount]:
    """Return a per-day count of completed Pomodoros for the given local month.

    `pomodoros` is expected to already be scoped to the User; any Pomodoro
    whose local day (per `time_zone`) falls outside `year`/`month` is ignored,
    so a wider input range is tolerated. Only days with at least one completed
    Pomodoro are returned, sorted by day.
    """
    zone = ZoneInfo(time_zone)
    counts: dict[date, int] = {}
    for pomodoro in pomodoros:
        if pomodoro.status is not PomodoroStatus.COMPLETED:
            continue
        local_day = pomodoro.ended_at.astimezone(zone).date()
        if local_day.year == year and local_day.month == month:
            counts[local_day] = counts.get(local_day, 0) + 1
    return [DayCount(day=day, completed_count=count) for day, count in sorted(counts.items())]


@dataclass(frozen=True)
class TaskDaySummary:
    """One Task's contribution to a single local day: count and dedicated time."""

    task: Task
    completed_count: int
    dedicated_seconds: int


def day_detail(
    pomodoros: Sequence[Pomodoro],
    tasks: Sequence[Task],
    local_day: date,
    time_zone: str,
    name_query: str = "",
    selected_tags: Sequence[TagId | str] = (),
) -> list[TaskDaySummary]:
    """Aggregate, per Task worked on `local_day`, its completed count and dedicated time.

    Dedicated time sums `completed` and `interrupted_logged` Pomodoros (story
    79); the completed count only counts `completed` ones. `tasks` must
    include every Task referenced by `pomodoros` regardless of archived
    status, since Archived Tasks still appear in History for days they were
    worked (story 81). The result is filtered with the same `filter_tasks`
    contract used by the Active/Archived tabs (story 82), in the order Tasks
    were first worked that day.
    """
    zone = ZoneInfo(time_zone)
    tasks_by_id: dict[TaskId, Task] = {task.id: task for task in tasks}
    completed_counts: dict[TaskId, int] = {}
    dedicated_seconds: dict[TaskId, int] = {}
    worked_order: list[TaskId] = []

    for pomodoro in pomodoros:
        if pomodoro.status not in _DEDICATED_STATUSES:
            continue
        if pomodoro.ended_at.astimezone(zone).date() != local_day:
            continue
        if pomodoro.task_id not in dedicated_seconds:
            worked_order.append(pomodoro.task_id)
            dedicated_seconds[pomodoro.task_id] = 0
        dedicated_seconds[pomodoro.task_id] += pomodoro.duration_seconds
        if pomodoro.status is PomodoroStatus.COMPLETED:
            completed_counts[pomodoro.task_id] = completed_counts.get(pomodoro.task_id, 0) + 1

    worked_tasks = [tasks_by_id[task_id] for task_id in worked_order if task_id in tasks_by_id]
    filtered_tasks = filter_tasks(worked_tasks, name_query, selected_tags)

    return [
        TaskDaySummary(
            task=task,
            completed_count=completed_counts.get(task.id, 0),
            dedicated_seconds=dedicated_seconds[task.id],
        )
        for task in filtered_tasks
    ]
