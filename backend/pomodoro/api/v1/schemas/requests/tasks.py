"""Inbound payloads for `api.v1.routers.tasks` (CES-4, T10).

`text` carries no length `Field(...)` constraint of its own: emptiness and the
200-character maximum are each already a single domain rule
(`core.tasks._validate_text`), and duplicating a second check here would risk
drifting out of sync with it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CreateTaskRequest(BaseModel):
    """POST /api/v1/tasks payload."""

    model_config = ConfigDict(extra="forbid")

    text: str


class EditTaskTextRequest(BaseModel):
    """PUT /api/v1/tasks/{task_id} payload."""

    model_config = ConfigDict(extra="forbid")

    text: str
