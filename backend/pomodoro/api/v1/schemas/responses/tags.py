"""Outbound payloads for `api.v1.routers.tags` (CES-4, T12).

Mirrors `core.entities.Tag`. A Tag with zero Tasks still appears here - the
catalog never prunes an orphaned Tag (`core.tags.delete_tag`'s docstring).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TagResponse(BaseModel):
    """A single Tag, as returned by every `api.v1.routers.tags` endpoint."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
