"""Unit tests for the settings module (CES-76)."""

from __future__ import annotations

import pytest

from pomodoro.entrypoints.settings import Settings, get_settings

pytestmark = pytest.mark.unit


def test_database_url_reads_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("database_url", "sqlite:///./lowercase.db")

    assert Settings().database_url == "sqlite:///./lowercase.db"


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
