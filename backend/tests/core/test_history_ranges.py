"""Unit tests for the pure local-month/local-day UTC range rules (T18)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pomodoro.core.history import local_day_utc_range, local_month_utc_range

pytestmark = pytest.mark.unit


def test_local_month_utc_range_covers_a_month_behind_utc() -> None:
    start, end = local_month_utc_range(2026, 3, time_zone="America/Argentina/Buenos_Aires")

    assert start == datetime(2026, 3, 1, 3, 0, tzinfo=UTC)
    assert end == datetime(2026, 4, 1, 3, 0, tzinfo=UTC)


def test_local_month_utc_range_handles_december_rolling_into_next_year() -> None:
    start, end = local_month_utc_range(2026, 12, time_zone="UTC")

    assert start == datetime(2026, 12, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)


def test_local_day_utc_range_covers_exactly_24_hours_ahead_of_utc() -> None:
    start, end = local_day_utc_range(date(2026, 3, 15), time_zone="Europe/Paris")

    assert start == datetime(2026, 3, 14, 23, 0, tzinfo=UTC)
    assert end == datetime(2026, 3, 15, 23, 0, tzinfo=UTC)
