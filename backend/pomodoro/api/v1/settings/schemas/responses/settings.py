"""CES-4 · outbound payload for GET and PATCH /api/v1/settings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SettingsResponse(BaseModel):
    """The caller's Alarm, notification, and time-zone preferences."""

    model_config = ConfigDict(extra="forbid")

    alarm_enabled: bool
    notifications_enabled: bool
    time_zone: str
