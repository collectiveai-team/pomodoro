"""Shared fixtures: force an in-memory SQLite database for every test.

Keeps the deterministic suite from touching a real database file (CONVENTIONS.md
test strategy) now that the DB-session dependency is wired into request handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pomodoro.entrypoints import dependencies
from pomodoro.entrypoints.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _in_memory_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    get_settings.cache_clear()
    dependencies.get_engine.cache_clear()
    yield
    get_settings.cache_clear()
    dependencies.get_engine.cache_clear()
