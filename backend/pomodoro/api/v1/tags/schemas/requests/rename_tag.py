"""CES-4 · inbound payload for PATCH /api/v1/tags/{tag_id}."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RenameTagRequest(BaseModel):
    """Rename-Tag payload: the new name, validated under the same rules as creation."""

    model_config = ConfigDict(extra="forbid")

    name: str
