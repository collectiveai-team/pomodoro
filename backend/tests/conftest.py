"""Shared fixtures: force an in-memory SQLite database for every test.

Keeps the deterministic suite from touching a real database file (CONVENTIONS.md
test strategy) now that the DB-session dependency is wired into request handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from pomodoro.database.tables import SQLModel
from pomodoro.entrypoints import dependencies
from pomodoro.entrypoints.app import create_app
from pomodoro.entrypoints.dependencies import get_engine
from pomodoro.entrypoints.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sqlalchemy.engine import Engine

PASSWORD = "correct horse battery staple"
TIME_ZONE = "America/Bogota"


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


def _build_anonymous_client() -> TestClient:
    # `set_session_cookie` sets `Secure`, so a plain `http://testserver` TestClient would
    # store the cookie but never resend it - `https://testserver` makes the round trip work.
    return TestClient(create_app(), base_url="https://testserver")


@pytest.fixture
def anonymous_client() -> TestClient:
    return _build_anonymous_client()


@pytest.fixture
def make_client() -> Callable[..., TestClient]:
    """Build a factory for a registered `TestClient`, so a test can create more than one User."""

    def _make(*, email: str = "someone@example.com") -> TestClient:
        test_client = _build_anonymous_client()
        test_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": PASSWORD, "time_zone": TIME_ZONE},
        )
        return test_client

    return _make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


@pytest.fixture
def _schema(_in_memory_database: None) -> Engine:
    # Explicitly depend on `_in_memory_database` so it runs first: it sets DATABASE_URL
    # and clears the cached engine.
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine
