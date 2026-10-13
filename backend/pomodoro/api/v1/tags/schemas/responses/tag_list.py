"""CES-4 · outbound payload for GET /api/v1/tags."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from pomodoro.api.v1.tags.schemas.responses.tag import TagResponse


class TagListResponse(BaseModel):
    """The caller's full Tag catalog."""

    model_config = ConfigDict(extra="forbid")

    tags: list[TagResponse]
