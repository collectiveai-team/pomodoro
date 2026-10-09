"""CES-4 · inbound payload for POST /api/v1/auth/register."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """Register payload.

    Email format and password length get their own domain errors with clear, per-field
    messages (`core.users`), so neither field carries a pydantic constraint here: a generic
    422 would replace the message the spec requires.
    """

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    time_zone: str = Field(min_length=1, description="Browser-detected IANA time zone.")
