"""Unit tests for the session guard: /me, /logout, 401 enforcement (Stories 7-8, 11, 13)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"


def _register(client: TestClient, *, email: str, password: str) -> None:
    client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "time_zone": "America/Argentina/Buenos_Aires"},
    )


def test_me_without_a_session_cookie_is_rejected(client: TestClient) -> None:
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_me_returns_the_caller_own_public_profile(client: TestClient) -> None:
    _register(client, email="owner@example.com", password="correct-horse-battery")

    response = client.get(ME_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "owner@example.com"
    assert "email_key" not in body
    assert "password" not in response.text
    assert "hash" not in response.text


def test_logout_revokes_the_session_so_its_cookie_stops_authenticating(
    client: TestClient,
) -> None:
    _register(client, email="owner@example.com", password="correct-horse-battery")

    logout_response = client.post(LOGOUT_URL)
    assert logout_response.status_code == 204

    me_response = client.get(ME_URL)
    assert me_response.status_code == 401


def test_one_user_session_cannot_read_another_user_me(client: TestClient) -> None:
    _register(client, email="first@example.com", password="first-password-123")
    first_session = client.cookies.get("session")

    client.cookies.clear()
    _register(client, email="second@example.com", password="second-password-123")

    client.cookies.set("session", first_session)
    response = client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["email"] == "first@example.com"


def test_an_expired_session_that_was_never_renewed_is_rejected(
    client: TestClient, fake_clock: FakeClock
) -> None:
    _register(client, email="owner@example.com", password="correct-horse-battery")

    fake_clock.advance(timedelta(days=31))  # past the 30-day expiry, with no renewing use

    assert client.get(ME_URL).status_code == 401


def test_session_slides_forward_on_use_past_its_original_30_day_expiry(
    client: TestClient, fake_clock: FakeClock
) -> None:
    _register(client, email="owner@example.com", password="correct-horse-battery")

    fake_clock.advance(timedelta(days=29))
    assert client.get(ME_URL).status_code == 200  # within the original window; also renews it

    fake_clock.advance(timedelta(days=29))  # 58 days in: past the original 30, not the renewal
    assert client.get(ME_URL).status_code == 200
