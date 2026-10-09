"""Outbound payload for `api.v1.routers.settings` (CES-4, T15).

Mirrors the User-editable preference subset of `core.entities.User` already
exposed by `UserResponse` (T9) - `time_zone`, `alarm_enabled` and
`notifications_enabled` - so a client has one consistent shape to read these
preferences from, independent of `/auth/me`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SettingsResponse(BaseModel):
    """GET/PATCH /api/v1/settings response."""

    model_config = ConfigDict(extra="forbid")

    time_zone: str
    alarm_enabled: bool
    notifications_enabled: bool
