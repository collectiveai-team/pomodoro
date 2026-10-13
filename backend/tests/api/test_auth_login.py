"""Unit tests for POST /api/v1/auth/login (CES-4, CES-17; User Stories 6-7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


def _register_payload(  # ast-grep-ignore: no-dict-return-annotation
    **overrides: str,
) -> dict[str, str]:
    payload = {
        "email": "visitor@example.com",
        "password": "correct-horse-battery-staple",
        "time_zone": "America/Argentina/Buenos_Aires",
    }
    payload.update(overrides)
    return payload


def test_login_with_correct_credentials_sets_a_session_cookie(client: TestClient) -> None:
    client.post(REGISTER_URL, json=_register_payload())

    response = client.post(
        LOGIN_URL,
        json={"email": "visitor@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": body["id"],
        "email": "visitor@example.com",
        "time_zone": "America/Argentina/Buenos_Aires",
        "alarm_enabled": True,
        "notifications_enabled": False,
        "created_at": body["created_at"],
    }

    token = response.cookies.get("session")
    assert token
    assert token not in response.text

    set_cookie = response.headers["set-cookie"].lower()
    for attribute in ("httponly", "secure", "samesite=lax", "path=/"):
        assert attribute in set_cookie


def test_login_with_a_wrong_password_gives_a_generic_error(client: TestClient) -> None:
    client.post(REGISTER_URL, json=_register_payload())

    response = client.post(
        LOGIN_URL, json={"email": "visitor@example.com", "password": "not-the-password"}
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "invalid_credentials"
    assert body["detail"] == "Email o contraseña incorrectos."


def test_login_with_an_unknown_email_gives_the_same_generic_error(client: TestClient) -> None:
    response = client.post(
        LOGIN_URL,
        json={"email": "nobody@example.com", "password": "correct-horse-battery-staple"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "invalid_credentials"
    assert body["detail"] == "Email o contraseña incorrectos."
