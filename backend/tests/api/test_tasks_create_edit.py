"""Unit tests for POST/PATCH/GET /api/v1/tasks (CES-4, CES-17; User Stories 14, 16-19, 21)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
TASKS_URL = "/api/v1/tasks"


def _register(client: TestClient, *, email: str = "owner@example.com") -> None:
    client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
    )


def _create(client: TestClient, text: str) -> dict:  # ast-grep-ignore: no-dict-return-annotation
    return client.post(TASKS_URL, json={"text": text}).json()


def test_create_task_succeeds_and_is_positioned_before_existing_active_tasks(
    client: TestClient,
) -> None:
    _register(client)

    first = client.post(TASKS_URL, json={"text": "Write report"})
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["text"] == "Write report"
    assert first_body["position"] == 0
    assert first_body["tag_ids"] == []
    assert first_body["archived_at"] is None
    assert "text_key" not in first.text

    second = client.post(TASKS_URL, json={"text": "Review PR"}).json()
    assert second["position"] < first_body["position"]
    assert second["position"] == -1  # negative positions are valid once a task precedes it


def test_get_tasks_lists_active_tasks_newest_first_by_position_then_id(
    client: TestClient,
) -> None:
    _register(client)
    _create(client, "A")
    _create(client, "B")
    _create(client, "C")

    response = client.get(TASKS_URL)

    assert response.status_code == 200
    texts = [task["text"] for task in response.json()]
    assert texts == ["C", "B", "A"]


def test_get_tasks_without_a_session_cookie_is_rejected(client: TestClient) -> None:
    response = client.get(TASKS_URL)

    assert response.status_code == 401


def test_create_task_rejects_empty_text_after_stripping(client: TestClient) -> None:
    _register(client)

    response = client.post(TASKS_URL, json={"text": "   "})

    assert response.status_code == 422
    assert response.json()["code"] == "empty_task_text"


def test_create_task_rejects_text_over_200_characters(client: TestClient) -> None:
    _register(client)

    response = client.post(TASKS_URL, json={"text": "x" * 201})

    assert response.status_code == 422
    assert response.json()["code"] == "task_text_too_long"


def test_create_task_rejects_duplicate_text_among_active_tasks_ignoring_case_and_whitespace(
    client: TestClient,
) -> None:
    _register(client)
    _create(client, "Write report")

    response = client.post(TASKS_URL, json={"text": "  WRITE REPORT  "})

    assert response.status_code == 422
    assert response.json()["code"] == "duplicate_task_text"


def test_edit_task_updates_its_text(client: TestClient) -> None:
    _register(client)
    task = _create(client, "Write report")

    response = client.patch(f"{TASKS_URL}/{task['id']}", json={"text": "Write the report"})

    assert response.status_code == 200
    assert response.json()["text"] == "Write the report"

    listed = client.get(TASKS_URL).json()
    assert listed[0]["text"] == "Write the report"


def test_edit_task_rejects_empty_text(client: TestClient) -> None:
    _register(client)
    task = _create(client, "Write report")

    response = client.patch(f"{TASKS_URL}/{task['id']}", json={"text": "  "})

    assert response.status_code == 422
    assert response.json()["code"] == "empty_task_text"


def test_edit_task_rejects_duplicate_text_among_the_caller_other_active_tasks(
    client: TestClient,
) -> None:
    _register(client)
    _create(client, "Write report")
    other = _create(client, "Review PR")

    response = client.patch(f"{TASKS_URL}/{other['id']}", json={"text": "write report"})

    assert response.status_code == 422
    assert response.json()["code"] == "duplicate_task_text"


def test_edit_task_allows_keeping_its_own_unchanged_text(client: TestClient) -> None:
    _register(client)
    task = _create(client, "Write report")

    response = client.patch(f"{TASKS_URL}/{task['id']}", json={"text": "Write report"})

    assert response.status_code == 200


def test_one_user_never_sees_another_user_tasks(client: TestClient) -> None:
    _register(client, email="first@example.com")
    _create(client, "First user's task")

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.get(TASKS_URL)

    assert response.status_code == 200
    assert response.json() == []


def test_one_user_cannot_edit_another_user_task(client: TestClient) -> None:
    _register(client, email="first@example.com")
    task = _create(client, "First user's task")

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.patch(f"{TASKS_URL}/{task['id']}", json={"text": "Hijacked"})

    assert response.status_code == 404
    assert response.json()["code"] == "task_not_found"
