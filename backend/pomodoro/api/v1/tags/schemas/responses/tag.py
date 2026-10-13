"""CES-4 · outbound payload for a Tag (list, rename)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TagResponse(BaseModel):
    """A Tag as returned to its owning caller — never `name_key`, never another User's."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
