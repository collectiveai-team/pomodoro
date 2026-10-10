"""CES-4 · inbound payload for PATCH /api/v1/settings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UpdateSettingsRequest(BaseModel):
    """Full-replace Settings payload: Alarm, notifications, and time zone."""

    model_config = ConfigDict(extra="forbid")

    alarm_enabled: bool
    notifications_enabled: bool
    time_zone: str
