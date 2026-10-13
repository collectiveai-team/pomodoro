"""HTTP tests proving Task query filters reach the shared core contract."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
TASKS_URL = "/api/v1/tasks"


def _register(client: TestClient) -> None:
    client.post(
        REGISTER_URL,
        json={
            "email": "owner@example.com",
            "password": "correct-horse-battery-staple",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
    )


def _create(client: TestClient, text: str) -> dict:  # ast-grep-ignore: no-dict-return-annotation
    return client.post(TASKS_URL, json={"text": text}).json()


def _set_tags(  # ast-grep-ignore: no-dict-return-annotation
    client: TestClient, task_id: str, names: list[str]
) -> dict:
    return client.patch(f"{TASKS_URL}/{task_id}/tags", json={"names": names}).json()


def test_active_task_list_applies_text_and_repeated_tag_query_filters(client: TestClient) -> None:
    _register(client)
    work_report = _create(client, "Write report")
    personal_report = _create(client, "Review report")
    work_note = _create(client, "Write notes")
    work_tag_id = _set_tags(client, work_report["id"], ["Work"])["tag_ids"][0]
    personal_tag_id = _set_tags(client, personal_report["id"], ["Personal"])["tag_ids"][0]
    _set_tags(client, work_note["id"], ["Work"])

    response = client.get(
        TASKS_URL,
        params=[("q", "REPORT"), ("tags", work_tag_id), ("tags", personal_tag_id)],
    )

    assert response.status_code == 200
    assert [task["text"] for task in response.json()["tasks"]] == ["Review report", "Write report"]


def test_archived_task_list_accepts_the_no_tag_query_sentinel(client: TestClient) -> None:
    _register(client)
    tagged_task = _create(client, "Tagged archive")
    untagged_task = _create(client, "Untagged archive")
    _set_tags(client, tagged_task["id"], ["Work"])
    client.post(f"{TASKS_URL}/{tagged_task['id']}/archive")
    client.post(f"{TASKS_URL}/{untagged_task['id']}/archive")

    response = client.get(
        f"{TASKS_URL}/archived",
        params=[("q", "archive"), ("tags", "sin etiqueta")],
    )

    assert response.status_code == 200
    assert [task["text"] for task in response.json()["tasks"]] == ["Untagged archive"]
