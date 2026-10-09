"""Outbound shape for the health-check endpoint (CES-4, CES-79)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health-check payload — proves the app is up and its providers resolve."""

    model_config = ConfigDict(extra="forbid")

    status: str
    server_time: datetime
