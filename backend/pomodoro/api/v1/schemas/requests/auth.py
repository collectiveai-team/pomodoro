"""Inbound payloads for `api.v1.routers.auth` (CES-4).

Fields carry no length/format `Field(...)` constraints of their own: email syntax,
password length and time-zone validity are each already a single domain rule
(`core.auth.normalize_email`/`hash_password`, `core.time_zone.validate_time_zone`),
and duplicating a second check here would risk drifting out of sync with it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RegisterRequest(BaseModel):
    """POST /api/v1/auth/register payload."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    time_zone: str


class LoginRequest(BaseModel):
    """POST /api/v1/auth/login payload."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    """POST /api/v1/auth/change-password payload."""

    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    """POST /api/v1/auth/delete-account payload."""

    model_config = ConfigDict(extra="forbid")

    password: str
