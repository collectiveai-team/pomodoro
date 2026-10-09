"""Restore UTC awareness lost on SQLite's `DateTime(timezone=True)` round-trip.

ADR-0002 stores every timestamp as a timezone-aware UTC value, and every value
written through this app's repositories is already UTC before it reaches a
`sa.Column`. SQLite has no native datetime type, so SQLAlchemy's generic
`DateTime(timezone=True)` silently drops the offset on read back there (a row
fetched from SQLite comes back naive, even though it carried tzinfo at insert
time); PostgreSQL's `timestamptz` preserves it. `as_utc` makes both engines
look the same to callers: a value that is already aware is returned unchanged,
a naive one is treated as UTC (never any other zone), matching what this app
always writes.
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def as_utc(value: datetime) -> datetime:
    """Return `value` with UTC tzinfo attached, if it lost it on a SQLite round-trip."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
