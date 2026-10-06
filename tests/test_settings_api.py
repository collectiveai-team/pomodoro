"""HTTP-level tests for the Settings API: read and update alarm/notifications/time_zone.

Same `tmp_path`-backed SQLite setup as `test_tasks_api.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import as_other_user as _as_other_user
from tests.conftest import authed_session as _authed_session

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_get_settings_returns_defaults(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="America/Argentina/Buenos_Aires")

    response = s.client.get("/api/settings", cookies=s.cookies)

    assert response.status_code == 200
    assert response.json() == {
        "alarm_enabled": True,
        "notifications_enabled": True,
        "time_zone": "America/Argentina/Buenos_Aires",
    }


@pytest.mark.unit
def test_get_settings_requires_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.get("/api/settings")

    assert response.status_code == 401


@pytest.mark.unit
def test_get_settings_does_not_leak_other_user(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="America/Argentina/Buenos_Aires")
    other_client, other_cookies = _as_other_user(s)

    response = other_client.get("/api/settings", cookies=other_cookies)

    assert response.status_code == 200
    assert response.json()["time_zone"] == "UTC"


@pytest.mark.unit
def test_patch_settings_updates_a_single_field(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.patch("/api/settings", cookies=s.cookies, json={"alarm_enabled": False})

    assert response.status_code == 200
    body = response.json()
    assert body["alarm_enabled"] is False
    assert body["notifications_enabled"] is True
    assert body["time_zone"] == "America/Argentina/Buenos_Aires"


@pytest.mark.unit
def test_patch_settings_updates_subset_of_fields(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.patch(
        "/api/settings",
        cookies=s.cookies,
        json={"notifications_enabled": False, "time_zone": "UTC"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "alarm_enabled": True,
        "notifications_enabled": False,
        "time_zone": "UTC",
    }

    # Persisted, not just echoed back.
    follow_up = s.client.get("/api/settings", cookies=s.cookies)
    assert follow_up.json() == body


@pytest.mark.unit
def test_patch_settings_rejects_invalid_time_zone(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.patch("/api/settings", cookies=s.cookies, json={"time_zone": "Not/AZone"})

    assert response.status_code == 422
    # Untouched.
    assert s.client.get("/api/settings", cookies=s.cookies).json()["time_zone"] == (
        "America/Argentina/Buenos_Aires"
    )


@pytest.mark.unit
def test_patch_settings_requires_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.patch(
        "/api/settings",
        json={"alarm_enabled": False},
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 401


@pytest.mark.unit
def test_patch_settings_does_not_affect_other_user(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="America/Argentina/Buenos_Aires")
    other_client, other_cookies = _as_other_user(s)

    response = other_client.patch(
        "/api/settings", cookies=other_cookies, json={"time_zone": "Asia/Tokyo"}
    )

    assert response.status_code == 200
    assert (
        s.client.get("/api/settings", cookies=s.cookies).json()["time_zone"]
        == "America/Argentina/Buenos_Aires"
    )
