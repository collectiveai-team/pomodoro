"""CES-4 · inbound payload for PATCH /api/v1/tags/{tag_id}."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pomodoro.core.tags import TagColor


class UpdateTagRequest(BaseModel):
    """Partial Tag update: any omitted field keeps its current value; an empty body is a no-op."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    color: TagColor | None = None
