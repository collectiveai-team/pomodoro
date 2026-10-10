"""Timezone-aware UTC conversion at the portable database seam (ADR-0002)."""

from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """Return `value` normalized to aware UTC, rejecting timestamps without a time zone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Database timestamps must be timezone-aware.")
    return value.astimezone(UTC)
