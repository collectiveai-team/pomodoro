"""CES-4 · inbound payload for PUT /api/v1/tasks/reorder."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReorderTasksRequest(BaseModel):
    """The caller's full ordered list of Active Task ids; rewritten as `position` 0..n-1."""

    model_config = ConfigDict(extra="forbid")

    task_ids: list[UUID]
