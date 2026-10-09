"""The one error-response shape every API v1 exception handler returns (CES-4, CES-79)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Outbound error envelope — forbids extras so the contract stays exactly this shape."""

    model_config = ConfigDict(extra="forbid")

    detail: str = Field(..., description="Human-readable error message.")
    code: str = Field(..., description="Machine-readable error code.")
