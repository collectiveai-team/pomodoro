"""CES-4 · outbound payload for GET /api/v1/tasks and GET /api/v1/tasks/archived."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pomodoro.api.v1.tasks.schemas.responses.task import TaskResponse


class TaskListResponse(BaseModel):
    """A page of Tasks plus both tab-badge counts (Active/Archived)."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[TaskResponse]
    active_count: int
    archived_count: int
