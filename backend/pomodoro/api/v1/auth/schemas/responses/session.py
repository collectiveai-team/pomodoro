"""CES-4 · outbound payload once a session is established (register, and later login)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """The caller's public profile — never the password hash nor the session token."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    time_zone: str
    alarm_enabled: bool
    notifications_enabled: bool
    created_at: datetime
