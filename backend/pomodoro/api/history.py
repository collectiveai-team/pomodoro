"""History API: the monthly heatmap and a single day's Task detail.

Per the house convention (api/<area> owns router + schemas + use case), the
orchestration lives here; `pomodoro.core.history` supplies the framework-free
aggregation rule and `pomodoro.api.session` supplies the authenticated `User`
every route below requires. `TaskRepository`/`TagRepository`/`PomodoroRepository`
are reused from `pomodoro.api.tasks` rather than wired a second time.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from pomodoro.api.session import require_session
from pomodoro.api.tasks import get_pomodoro_repository, get_tag_repository, get_task_repository
from pomodoro.core.entities import Tag, TagId, User
from pomodoro.core.filtering import SIN_ETIQUETA
from pomodoro.core.history import (
    DayCount,
    TaskDaySummary,
    day_detail,
    month_bounds_utc,
    monthly_heatmap,
)
from pomodoro.core.history import day_bounds_utc as _day_bounds_utc
from pomodoro.core.repositories import PomodoroRepository, TagRepository, TaskRepository
from pomodoro.core.tags import find_tag_by_name

router = APIRouter(prefix="/api/history", tags=["history"])

UserDep = Annotated[User, Depends(require_session)]
TaskRepoDep = Annotated[TaskRepository, Depends(get_task_repository)]
TagRepoDep = Annotated[TagRepository, Depends(get_tag_repository)]
PomodoroRepoDep = Annotated[PomodoroRepository, Depends(get_pomodoro_repository)]


def _resolve_selected_tags(names: list[str], catalog: list[Tag]) -> list[TagId | str]:
    resolved: list[TagId | str] = []
    for name in names:
        if name == SIN_ETIQUETA:
            resolved.append(SIN_ETIQUETA)
            continue
        tag = find_tag_by_name(name, catalog)
        if tag is not None:
            resolved.append(tag.id)
    return resolved


def _tag_names(tag_ids: tuple[TagId, ...], catalog: list[Tag]) -> list[str]:
    by_id = {tag.id: tag.name for tag in catalog}
    return [by_id[tag_id] for tag_id in tag_ids if tag_id in by_id]


class MonthDayPublic(BaseModel):
    """One local day's completed-Pomodoro count, for the heatmap."""

    day: date
    completed_count: int

    @classmethod
    def from_entity(cls, day_count: DayCount) -> MonthDayPublic:
        return cls(day=day_count.day, completed_count=day_count.completed_count)


class DayTaskSummaryPublic(BaseModel):
    """One Task's contribution to a single day: completed count and dedicated time."""

    task_id: int
    text: str
    tags: list[str]
    completed_count: int
    dedicated_seconds: int

    @classmethod
    def from_entity(cls, summary: TaskDaySummary, *, catalog: list[Tag]) -> DayTaskSummaryPublic:
        return cls(
            task_id=summary.task.id,
            text=summary.task.text,
            tags=_tag_names(summary.task.tag_ids, catalog),
            completed_count=summary.completed_count,
            dedicated_seconds=summary.dedicated_seconds,
        )


@router.get("/month")
def get_month_heatmap(
    user: UserDep,
    pomodoro_repo: PomodoroRepoDep,
    year: Annotated[int, Query(ge=1, le=9999)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> list[MonthDayPublic]:
    """Return the User's per-day completed-Pomodoro count for the requested local month."""
    start, end = month_bounds_utc(year, month, user.time_zone)
    pomodoros = pomodoro_repo.list_between(user.id, start, end)
    counts = monthly_heatmap(pomodoros, year, month, user.time_zone)
    return [MonthDayPublic.from_entity(count) for count in counts]


@router.get("/day")
def get_day_detail(
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    date: Annotated[date, Query()],
    tags: Annotated[list[str], Query(default_factory=list)],
    text: str = "",
) -> list[DayTaskSummaryPublic]:
    """Return, per Task worked on `date`, its completed count and dedicated time.

    Includes Archived Tasks worked that day (story 81) and accepts the same
    name/tags filter query params as `/api/tasks` (story 82, 45).
    """
    start, end = _day_bounds_utc(date, user.time_zone)
    pomodoros = pomodoro_repo.list_between(user.id, start, end)
    tasks = task_repo.list_active(user.id) + task_repo.list_archived(user.id)
    catalog = tag_repo.list(user.id)
    selected_tags = _resolve_selected_tags(tags, catalog)
    summaries = day_detail(pomodoros, tasks, date, user.time_zone, text, selected_tags)
    return [DayTaskSummaryPublic.from_entity(summary, catalog=catalog) for summary in summaries]
