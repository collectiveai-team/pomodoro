"""CES-4 · inbound payload for DELETE /api/v1/auth/me."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DeleteAccountRequest(BaseModel):
    """Delete-account payload: the current password, required to confirm deletion."""

    model_config = ConfigDict(extra="forbid")

    password: str
