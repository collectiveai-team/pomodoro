"""Rate-limit keys use the client IP the trusted frontend proxy saw (User Story 12).

The backend is reachable only through the frontend's rewrite, which appends the address it
received the request from to `X-Forwarded-For`. That rightmost entry is the only one the client
cannot write, so it is the IP half of the key; everything left of it is client-supplied.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from pomodoro.api.v1.dependencies import get_clock
from pomodoro.database.session import get_db_session
from pomodoro.entrypoints.app import create_app
from sqlmodel import Session

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy import Engine
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit

LOGIN_URL = "/api/v1/auth/login"
_PROXY_PEER = ("172.18.0.3", 41000)  # the frontend container, a private address
_WRONG = {"email": "visitor@example.com", "password": "wrong-password"}


def _client_from(peer: tuple[str, int], db_engine: Engine, fake_clock: FakeClock) -> TestClient:
    def _session() -> Iterator[Session]:
        with Session(db_engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_clock] = lambda: fake_clock
    return TestClient(app, base_url="https://testserver", client=peer)


def _fail_login(client: TestClient, forwarded_for: str) -> int:
    return client.post(
        LOGIN_URL, json=_WRONG, headers={"X-Forwarded-For": forwarded_for}
    ).status_code


def test_clients_behind_the_proxy_are_limited_separately(
    db_engine: Engine, fake_clock: FakeClock
) -> None:
    client = _client_from(_PROXY_PEER, db_engine, fake_clock)
    for _ in range(5):
        _fail_login(client, "198.51.100.7")

    assert _fail_login(client, "198.51.100.7") == 429
    assert _fail_login(client, "198.51.100.8") == 401


def test_a_forged_forwarded_for_prefix_does_not_escape_the_limit(
    db_engine: Engine, fake_clock: FakeClock
) -> None:
    client = _client_from(_PROXY_PEER, db_engine, fake_clock)
    # A client on a private network (here the Docker gateway) rotates a forged prefix; the proxy
    # appends the address it really saw, which never changes.
    for attempt in range(5):
        _fail_login(client, f"203.0.113.{attempt}, 192.168.65.1")

    assert _fail_login(client, "203.0.113.99, 192.168.65.1") == 429


def test_an_untrusted_peer_cannot_choose_its_ip_with_the_header(
    db_engine: Engine, fake_clock: FakeClock
) -> None:
    client = _client_from(("203.0.113.9", 52000), db_engine, fake_clock)
    for attempt in range(5):
        _fail_login(client, f"198.51.100.{attempt}")

    assert _fail_login(client, "198.51.100.99") == 429
