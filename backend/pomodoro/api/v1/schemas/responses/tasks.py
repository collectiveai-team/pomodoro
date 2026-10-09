"""Outbound payloads for `api.v1.routers.tasks` (CES-4, T10).

Mirrors `core.entities.Task` plus two derived fields no column stores:
`status` (derived from `archived_at`, per `Task.status`) and `deletable`
(whether the Task has any recorded Pomodoro, per `core.tasks.ensure_task_deletable`).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskResponse(BaseModel):
    """A single Task, as returned by every `api.v1.routers.tasks` endpoint."""

    model_config = ConfigDict(extra="forbid")

    id: int
    text: str
    position: int
    status: str
    created_at: datetime
    archived_at: datetime | None
    tag_ids: list[int]
    deletable: bool


class TaskListResponse(BaseModel):
    """GET /api/v1/tasks payload: the filtered page plus the tab-badge counts."""

    model_config = ConfigDict(extra="forbid")

    items: list[TaskResponse]
    active_count: int
    archived_count: int
