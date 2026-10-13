"""Production Clock adapter wired by the FastAPI app factory (ADR-0001)."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Real wall-clock adapter that always returns timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)
