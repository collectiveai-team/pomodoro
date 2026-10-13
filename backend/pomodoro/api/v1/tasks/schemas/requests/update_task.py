"""CES-4 · inbound payload for PATCH /api/v1/tasks/{task_id}."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UpdateTaskRequest(BaseModel):
    """Edit-Task payload: same validation rules as creation (`core.tasks`)."""

    model_config = ConfigDict(extra="forbid")

    text: str
