"""Unit tests for login/register rate limiting (CES-17; User Story 12)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

_EMAIL = "visitor@example.com"
_TIME_ZONE = "America/Argentina/Buenos_Aires"
_CORRECT_PASSWORD = "correct-horse-battery-staple"


def _register(client: TestClient) -> None:
    client.post(
        REGISTER_URL,
        json={"email": _EMAIL, "password": _CORRECT_PASSWORD, "time_zone": _TIME_ZONE},
    )


def test_login_is_blocked_with_429_after_five_failed_attempts(client: TestClient) -> None:
    _register(client)

    for _ in range(5):
        response = client.post(LOGIN_URL, json={"email": _EMAIL, "password": "wrong-password"})
        assert response.status_code == 401

    blocked = client.post(LOGIN_URL, json={"email": _EMAIL, "password": "wrong-password"})

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"


def test_login_rate_limit_resets_once_the_window_passes(
    client: TestClient, fake_clock: FakeClock
) -> None:
    _register(client)
    for _ in range(5):
        client.post(LOGIN_URL, json={"email": _EMAIL, "password": "wrong-password"})
    blocked = client.post(LOGIN_URL, json={"email": _EMAIL, "password": "wrong-password"})
    assert blocked.status_code == 429

    fake_clock.advance(timedelta(minutes=15, seconds=1))

    response = client.post(LOGIN_URL, json={"email": _EMAIL, "password": _CORRECT_PASSWORD})
    assert response.status_code == 200


def test_successful_logins_do_not_count_toward_the_rate_limit(client: TestClient) -> None:
    _register(client)

    for _ in range(10):
        response = client.post(LOGIN_URL, json={"email": _EMAIL, "password": _CORRECT_PASSWORD})
        assert response.status_code == 200


def test_a_different_email_is_not_blocked_by_another_emails_failures(
    client: TestClient,
) -> None:
    _register(client)
    for _ in range(6):
        client.post(LOGIN_URL, json={"email": _EMAIL, "password": "wrong-password"})

    response = client.post(
        LOGIN_URL, json={"email": "someone-else@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401  # a different key: not yet rate-limited


def test_register_is_blocked_with_429_after_five_failed_attempts(client: TestClient) -> None:
    payload = {"email": _EMAIL, "password": "short", "time_zone": _TIME_ZONE}

    for _ in range(5):
        response = client.post(REGISTER_URL, json=payload)
        assert response.status_code == 422

    blocked = client.post(REGISTER_URL, json=payload)

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
