"""CES-4 · outbound payload for a Task (create, edit, list)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskResponse(BaseModel):
    """A Task as returned to its owning caller — never another User's, never `text_key`."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    text: str
    position: int
    tag_ids: list[UUID]
    created_at: datetime
    archived_at: datetime | None
