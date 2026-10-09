"""Response shape for GET /api/v1/health (CES-4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Outbound payload confirming the API is up."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
