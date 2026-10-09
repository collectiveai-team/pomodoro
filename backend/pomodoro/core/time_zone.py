"""The one IANA time-zone validation rule (core, T9).

Shared by register (T9) and the later Settings API (T15) so "is this a valid time
zone" exists in exactly one place (CES-16) - a prior build let an unvalidated
`time_zone` through registration, later breaking History/summary grouping.
"""

from __future__ import annotations

from zoneinfo import available_timezones

from pomodoro.core.errors import InvalidTimeZoneError


def validate_time_zone(time_zone: str) -> None:
    """Raise `InvalidTimeZoneError` unless `time_zone` is a valid IANA zone name."""
    if time_zone not in available_timezones():
        raise InvalidTimeZoneError(time_zone)
