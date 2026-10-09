"""Inbound payloads for `api.v1.routers.tags` (CES-4, T12).

`name` carries no length `Field(...)` constraint of its own: emptiness is
already a single domain rule (`core.tags._validate_name`), and duplicating a
second check here would risk drifting out of sync with it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RenameTagRequest(BaseModel):
    """PUT /api/v1/tags/{tag_id} payload."""

    model_config = ConfigDict(extra="forbid")

    name: str
