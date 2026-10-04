"""Column types shared by the table definitions in this layer only."""

from datetime import UTC, datetime
from typing import Any

from sqlmodel import DateTime, TypeDecorator


class UTCDateTime(TypeDecorator):
    """Stores timezone-aware UTC timestamps; round-trips as aware `datetime`.

    PostgreSQL's `timestamptz` preserves the offset natively. SQLite has no
    timezone-aware column type, so a value read back from it loses `tzinfo`;
    this decorator reattaches UTC on the way out so both engines agree.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime values stored in the database must be timezone-aware")
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
