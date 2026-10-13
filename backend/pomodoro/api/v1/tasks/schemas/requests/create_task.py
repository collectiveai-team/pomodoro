"""CES-4 · inbound payload for POST /api/v1/tasks."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CreateTaskRequest(BaseModel):
    """Create-Task payload.

    Empty/over-length text gets its own domain error with a clear message (`core.tasks`), so
    `text` carries no pydantic length constraint here.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
