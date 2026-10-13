"""CES-4 · inbound payload for PATCH /api/v1/settings."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class UpdateSettingsRequest(BaseModel):
    """Partial Settings payload: only the sent fields change; omitted ones keep their value.

    At least one field is required, and a sent field may not be null.
    """

    model_config = ConfigDict(extra="forbid")

    alarm_enabled: bool | None = None
    notifications_enabled: bool | None = None
    time_zone: str | None = None

    @model_validator(mode="after")
    def _at_least_one_non_null_field(self) -> Self:
        if not self.model_fields_set:
            msg = "at least one setting must be provided"
            raise ValueError(msg)
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                msg = f"{name} must not be null"
                raise ValueError(msg)
        return self
