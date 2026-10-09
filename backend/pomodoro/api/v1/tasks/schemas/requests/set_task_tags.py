"""CES-4 · inbound payload for PATCH /api/v1/tasks/{task_id}/tags."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SetTaskTagsRequest(BaseModel):
    """The Task's full Tag list by name; each name is created or reused by normalized key."""

    model_config = ConfigDict(extra="forbid")

    names: list[str]
