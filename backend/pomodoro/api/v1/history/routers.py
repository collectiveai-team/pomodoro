"""CES-17 · History endpoints: month summary heatmap and day detail (T18).

Same FastAPI type-hint-resolution caveat as `tasks/routers.py`: every annotated name must be a
real, module-level import, never `TYPE_CHECKING`-only.
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from pomodoro.api.v1.auth.dependencies import get_current_user
from pomodoro.api.v1.history.schemas.responses.day_detail import (
    DayDetailResponse,
    DayTaskSummaryResponse,
)
from pomodoro.api.v1.history.schemas.responses.month_summary import (
    MonthDaySummaryResponse,
    MonthSummaryResponse,
)
from pomodoro.api.v1.history.use_cases import day_detail, month_summary
from pomodoro.core.tags import TagId
from pomodoro.core.task_filtering import TaskTagFilter
from pomodoro.core.tasks import TaskRepository
from pomodoro.core.timer import PomodoroRepository
from pomodoro.core.users import User
from pomodoro.database.repositories.pomodoro import get_pomodoro_repository
from pomodoro.database.repositories.task import get_task_repository

router = APIRouter(prefix="/history", tags=["history"])


def _selected_tag_filters(
    tags: list[UUID | Literal["sin etiqueta"]] | None,
) -> tuple[TaskTagFilter, ...]:
    return tuple(TagId(tag) if isinstance(tag, UUID) else tag for tag in tags or ())


@router.get("/month")
def read_month_summary(
    year: int = Query(..., ge=1, le=9999),
    month: int = Query(..., ge=1, le=12),
    user: User = Depends(get_current_user),
    pomodoro_repository: PomodoroRepository = Depends(get_pomodoro_repository),
) -> MonthSummaryResponse:
    """Return every day's completed-Pomodoro count for the caller's local `year`/`month`."""
    summary = month_summary(
        user=user, year=year, month=month, pomodoro_repository=pomodoro_repository
    )
    return MonthSummaryResponse(
        year=summary.year,
        month=summary.month,
        days=[
            MonthDaySummaryResponse(day=day.day, completed_count=day.completed_count)
            for day in summary.days
        ],
    )


@router.get("/day")
def read_day_detail(
    day: date = Query(..., alias="date"),
    q: str | None = None,
    tags: list[UUID | Literal["sin etiqueta"]] | None = Query(default=None),
    user: User = Depends(get_current_user),
    pomodoro_repository: PomodoroRepository = Depends(get_pomodoro_repository),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> DayDetailResponse:
    """Return the caller's per-Task completed count and dedicated time for the local day."""
    detail = day_detail(
        user=user,
        day=day,
        name_query=q,
        selected_tags=_selected_tag_filters(tags),
        pomodoro_repository=pomodoro_repository,
        task_repository=task_repository,
    )
    return DayDetailResponse(
        day=detail.day,
        completed_count=detail.completed_count,
        tasks=[
            DayTaskSummaryResponse(
                task_id=summary.task.id,
                text=summary.task.text,
                completed_count=summary.completed_count,
                dedicated_seconds=summary.dedicated_seconds,
            )
            for summary in detail.tasks
        ],
    )
