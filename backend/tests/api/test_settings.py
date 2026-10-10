"""Unit tests for Settings: read/update Alarm, notifications, time zone (CES-4, CES-17; T15)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
SETTINGS_URL = "/api/v1/settings"
ME_URL = "/api/v1/auth/me"


def _register(client: TestClient, *, email: str = "owner@example.com") -> None:
    client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
    )


def test_get_settings_returns_the_registration_defaults(client: TestClient) -> None:
    _register(client)

    response = client.get(SETTINGS_URL)

    assert response.status_code == 200
    assert response.json() == {
        "alarm_enabled": True,
        "notifications_enabled": False,
        "time_zone": "America/Argentina/Buenos_Aires",
    }


def test_round_trip_update_persists_and_is_reflected_immediately(client: TestClient) -> None:
    _register(client)

    update = client.patch(
        SETTINGS_URL,
        json={
            "alarm_enabled": False,
            "notifications_enabled": True,
            "time_zone": "Europe/Berlin",
        },
    )

    assert update.status_code == 200
    expected = {
        "alarm_enabled": False,
        "notifications_enabled": True,
        "time_zone": "Europe/Berlin",
    }
    assert update.json() == expected

    # A derived view read right after the update (no separate recompute step) sees it too.
    assert client.get(SETTINGS_URL).json() == expected
    assert client.get(ME_URL).json()["time_zone"] == "Europe/Berlin"


def test_update_rejects_an_invalid_iana_time_zone(client: TestClient) -> None:
    _register(client)

    response = client.patch(
        SETTINGS_URL,
        json={
            "alarm_enabled": True,
            "notifications_enabled": True,
            "time_zone": "Not/AZone",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_time_zone"
    assert "Not/AZone" in body["detail"]

    # Nothing was persisted by the rejected update.
    unchanged = client.get(SETTINGS_URL)
    assert unchanged.json()["time_zone"] == "America/Argentina/Buenos_Aires"
    assert unchanged.json()["notifications_enabled"] is False


def test_get_settings_without_a_session_cookie_is_rejected(client: TestClient) -> None:
    response = client.get(SETTINGS_URL)

    assert response.status_code == 401


def test_update_settings_without_a_session_cookie_is_rejected(client: TestClient) -> None:
    response = client.patch(
        SETTINGS_URL,
        json={"alarm_enabled": False, "notifications_enabled": False, "time_zone": "UTC"},
    )

    assert response.status_code == 401


def test_settings_are_scoped_per_user(client: TestClient) -> None:
    _register(client, email="first@example.com")
    client.patch(
        SETTINGS_URL,
        json={"alarm_enabled": False, "notifications_enabled": True, "time_zone": "UTC"},
    )

    client.cookies.clear()
    _register(client, email="second@example.com")

    second_settings = client.get(SETTINGS_URL).json()
    assert second_settings == {
        "alarm_enabled": True,
        "notifications_enabled": False,
        "time_zone": "America/Argentina/Buenos_Aires",
    }
