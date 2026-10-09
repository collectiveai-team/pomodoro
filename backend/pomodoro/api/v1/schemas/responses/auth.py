"""Outbound payload for `api.v1.routers.auth` (CES-4).

Mirrors `core.entities.User` minus anything internal: `password_hash` and
`email_key` only ever exist on the SQL row (`database.tables.User`), never on
the `User` dataclass every repository method here maps from, so there is
nothing secret to accidentally leak through this response.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """Register/login success payload and the GET /me response."""

    model_config = ConfigDict(extra="forbid")

    id: int
    email: str
    created_at: datetime
    time_zone: str
    alarm_enabled: bool
    notifications_enabled: bool
