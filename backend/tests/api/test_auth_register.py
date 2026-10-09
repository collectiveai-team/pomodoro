"""Unit tests for POST /api/v1/auth/register (CES-4, CES-17; User Stories 1-5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"


def _payload(**overrides: str) -> dict[str, str]:  # ast-grep-ignore: no-dict-return-annotation
    payload = {
        "email": "visitor@example.com",
        "password": "correct-horse-battery-staple",
        "time_zone": "America/Argentina/Buenos_Aires",
    }
    payload.update(overrides)
    return payload


def test_register_creates_user_and_logs_in_with_a_session_cookie(client: TestClient) -> None:
    response = client.post(REGISTER_URL, json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "email": "visitor@example.com",
        "time_zone": "America/Argentina/Buenos_Aires",
        "alarm_enabled": True,
        "notifications_enabled": False,
        "created_at": body["created_at"],
    }
    assert "password" not in response.text
    assert "hash" not in response.text

    token = response.cookies.get("session")
    assert token
    assert token not in response.text

    set_cookie = response.headers["set-cookie"].lower()
    for attribute in ("httponly", "secure", "samesite=lax", "path=/"):
        assert attribute in set_cookie


def test_register_rejects_a_duplicate_email_ignoring_case_and_whitespace(
    client: TestClient,
) -> None:
    client.post(REGISTER_URL, json=_payload(email="Visitor@Example.com"))

    response = client.post(REGISTER_URL, json=_payload(email="  visitor@example.com  "))

    assert response.status_code == 422
    assert response.json()["code"] == "duplicate_email"


def test_register_rejects_an_invalid_email_format(client: TestClient) -> None:
    response = client.post(REGISTER_URL, json=_payload(email="not-an-email"))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_email"


def test_register_rejects_a_password_shorter_than_8_characters(client: TestClient) -> None:
    response = client.post(REGISTER_URL, json=_payload(password="short1"))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_password_length"


def test_register_rejects_a_password_longer_than_128_characters(client: TestClient) -> None:
    response = client.post(REGISTER_URL, json=_payload(password="x" * 129))

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_password_length"
