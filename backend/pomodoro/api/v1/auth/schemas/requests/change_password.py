"""CES-4 · inbound payload for POST /api/v1/auth/change-password."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ChangePasswordRequest(BaseModel):
    """Change-password payload.

    Neither field carries a pydantic constraint: a wrong current password and an invalid new
    password length each get their own domain error with a clear message (`core.users`).
    """

    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str
