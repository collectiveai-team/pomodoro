"""Inbound payload for `api.v1.routers.settings` (CES-4, T15).

Every field is optional, so a client can update one preference without
resending the others - the ticket's acceptance criteria require reading and
updating each one independently. `time_zone`, when provided, carries no
length/format `Field(...)` constraint of its own: validity is already a single
domain rule (`core.time_zone.validate_time_zone`), reused unchanged from T9's
register rather than duplicated here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UpdateSettingsRequest(BaseModel):
    """PATCH /api/v1/settings payload."""

    model_config = ConfigDict(extra="forbid")

    time_zone: str | None = None
    alarm_enabled: bool | None = None
    notifications_enabled: bool | None = None
