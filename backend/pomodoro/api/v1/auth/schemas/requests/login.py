"""CES-4 · inbound payload for POST /api/v1/auth/login."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    """Login payload.

    Neither field carries a pydantic constraint: a mismatch on either one collapses into the
    same generic `InvalidCredentialsError`, so a per-field 422 would leak which one was wrong.
    """

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
