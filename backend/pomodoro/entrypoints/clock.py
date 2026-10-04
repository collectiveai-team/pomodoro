"""The real wall-clock `Clock` implementation, injected by the app factory."""

from datetime import UTC, datetime


class RealClock:
    """Wall-clock implementation of `pomodoro.core.clock.Clock`."""

    def now(self) -> datetime:
        return datetime.now(UTC)
