"""Unit tests for Tag assignment and the Tag catalog (CES-4, CES-17; User Stories 32-39)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
TASKS_URL = "/api/v1/tasks"
TAGS_URL = "/api/v1/tags"


def _register(client: TestClient, *, email: str = "owner@example.com") -> None:
    client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
    )


def _create_task(  # ast-grep-ignore: no-dict-return-annotation
    client: TestClient, text: str
) -> dict:
    return client.post(TASKS_URL, json={"text": text}).json()


def _set_tags(  # ast-grep-ignore: no-dict-return-annotation
    client: TestClient, task_id: str, names: list[str]
) -> dict:
    return client.patch(f"{TASKS_URL}/{task_id}/tags", json={"names": names}).json()


def test_assigning_a_tag_by_name_creates_it(client: TestClient) -> None:
    _register(client)
    task = _create_task(client, "Write report")

    response = client.patch(f"{TASKS_URL}/{task['id']}/tags", json={"names": ["Work"]})

    assert response.status_code == 200
    assert len(response.json()["tag_ids"]) == 1

    catalog = client.get(TAGS_URL).json()["tags"]
    assert [tag["name"] for tag in catalog] == ["Work"]


def test_assigning_a_tag_reuses_the_same_row_for_a_normalized_name_match(
    client: TestClient,
) -> None:
    _register(client)
    first_task = _create_task(client, "Write report")
    second_task = _create_task(client, "Review PR")

    first = _set_tags(client, first_task["id"], ["Trabajo"])
    second = _set_tags(client, second_task["id"], ["  trabajo  "])

    assert first["tag_ids"] == second["tag_ids"]
    assert len(client.get(TAGS_URL).json()["tags"]) == 1


def test_assigning_duplicate_names_in_one_request_resolves_to_one_tag(client: TestClient) -> None:
    _register(client)
    task = _create_task(client, "Write report")

    response = _set_tags(client, task["id"], ["Work", "work", "  WORK  "])

    assert len(response["tag_ids"]) == 1
    assert len(client.get(TAGS_URL).json()["tags"]) == 1


def test_two_users_can_share_a_tag_name_without_sharing_the_row(client: TestClient) -> None:
    _register(client, email="first@example.com")
    first_task = _create_task(client, "First user's task")
    first = _set_tags(client, first_task["id"], ["Work"])

    client.cookies.clear()
    _register(client, email="second@example.com")
    second_task = _create_task(client, "Second user's task")
    second = _set_tags(client, second_task["id"], ["Work"])

    assert first["tag_ids"] != second["tag_ids"]
    assert len(client.get(TAGS_URL).json()["tags"]) == 1


def test_set_task_tags_rejects_an_empty_name(client: TestClient) -> None:
    _register(client)
    task = _create_task(client, "Write report")

    response = client.patch(f"{TASKS_URL}/{task['id']}/tags", json={"names": ["  "]})

    assert response.status_code == 422
    assert response.json()["code"] == "empty_tag_name"


def test_set_task_tags_on_another_users_task_is_not_found(client: TestClient) -> None:
    _register(client, email="first@example.com")
    task = _create_task(client, "First user's task")

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.patch(f"{TASKS_URL}/{task['id']}/tags", json={"names": ["Work"]})

    assert response.status_code == 404
    assert response.json()["code"] == "task_not_found"


def test_setting_an_empty_name_list_clears_a_tasks_tags_and_keeps_the_orphaned_tag(
    client: TestClient,
) -> None:
    _register(client)
    task = _create_task(client, "Write report")
    _set_tags(client, task["id"], ["Work"])

    cleared = _set_tags(client, task["id"], [])

    assert cleared["tag_ids"] == []
    assert client.get(TASKS_URL).json()["tasks"][0]["tag_ids"] == []
    assert len(client.get(TAGS_URL).json()["tags"]) == 1


def test_renaming_a_tag_propagates_to_every_task_carrying_it(client: TestClient) -> None:
    _register(client)
    task = _create_task(client, "Write report")
    tag_id = _set_tags(client, task["id"], ["Work"])["tag_ids"][0]

    response = client.patch(f"{TAGS_URL}/{tag_id}", json={"name": "Job"})

    assert response.status_code == 200
    assert response.json() == {"id": tag_id, "name": "Job"}

    listed = client.get(TASKS_URL).json()["tasks"][0]
    assert listed["tag_ids"] == [tag_id]
    catalog = client.get(TAGS_URL).json()["tags"]
    assert catalog == [{"id": tag_id, "name": "Job"}]


def test_renaming_a_tag_to_a_normalized_collision_is_rejected(client: TestClient) -> None:
    _register(client)
    first_task = _create_task(client, "First task")
    second_task = _create_task(client, "Second task")
    work_tag_id = _set_tags(client, first_task["id"], ["Work"])["tag_ids"][0]
    _set_tags(client, second_task["id"], ["Job"])

    response = client.patch(f"{TAGS_URL}/{work_tag_id}", json={"name": "  JOB  "})

    assert response.status_code == 422
    assert response.json()["code"] == "duplicate_tag_name"


def test_renaming_a_tag_to_its_own_current_name_is_allowed(client: TestClient) -> None:
    _register(client)
    task = _create_task(client, "Write report")
    tag_id = _set_tags(client, task["id"], ["Work"])["tag_ids"][0]

    response = client.patch(f"{TAGS_URL}/{tag_id}", json={"name": "Work"})

    assert response.status_code == 200


def test_one_user_cannot_rename_another_users_tag(client: TestClient) -> None:
    _register(client, email="first@example.com")
    task = _create_task(client, "First user's task")
    tag_id = _set_tags(client, task["id"], ["Work"])["tag_ids"][0]

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.patch(f"{TAGS_URL}/{tag_id}", json={"name": "Hijacked"})

    assert response.status_code == 404
    assert response.json()["code"] == "tag_not_found"


def test_deleting_a_tag_removes_it_from_every_task_without_confirmation(
    client: TestClient,
) -> None:
    _register(client)
    first_task = _create_task(client, "First task")
    second_task = _create_task(client, "Second task")
    tag_id = _set_tags(client, first_task["id"], ["Work"])["tag_ids"][0]
    _set_tags(client, second_task["id"], ["Work"])

    response = client.delete(f"{TAGS_URL}/{tag_id}")

    assert response.status_code == 204
    tasks = client.get(TASKS_URL).json()["tasks"]
    assert all(task["tag_ids"] == [] for task in tasks)
    assert client.get(TAGS_URL).json()["tags"] == []


def test_one_user_cannot_delete_another_users_tag(client: TestClient) -> None:
    _register(client, email="first@example.com")
    task = _create_task(client, "First user's task")
    tag_id = _set_tags(client, task["id"], ["Work"])["tag_ids"][0]

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.delete(f"{TAGS_URL}/{tag_id}")

    assert response.status_code == 404
    assert response.json()["code"] == "tag_not_found"


def test_get_tags_without_a_session_cookie_is_rejected(client: TestClient) -> None:
    response = client.get(TAGS_URL)

    assert response.status_code == 401
