"""The single error-response shape every mapped domain error returns (CES-4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    """Outbound error payload returned by the app factory's DomainError handler."""

    model_config = ConfigDict(extra="forbid")

    detail: str
