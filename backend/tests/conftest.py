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
    # `get_rate_limiter` is process-wide (`@lru_cache`), and `TestClient` requests all share
    # the same `request.client.host` ("testclient") - without a per-test reset, failed-login
    # attempts recorded by one test's rate-limiting assertions would leak into the next test
    # using the same email (T9's `api/v1/auth` is the first ticket to exercise it through a
    # real request rather than a directly-constructed `RateLimiter()`).
    dependencies.get_rate_limiter.cache_clear()
    yield
    get_settings.cache_clear()
    dependencies.get_engine.cache_clear()
    dependencies.get_rate_limiter.cache_clear()
