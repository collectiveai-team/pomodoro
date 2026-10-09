"""Tests for the T10 `api/v1/tasks` router: list/create/edit/delete, filter, counts.

Drives the real app (`entrypoints.app.create_app`) through `TestClient` over an
in-memory SQLite database (the `_in_memory_database` conftest fixture), never a
mocked repository - matching T9's existing `api/v1` test style.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from pomodoro.database import tables
from pomodoro.database.tables import SQLModel
from pomodoro.entrypoints.app import create_app
from pomodoro.entrypoints.dependencies import get_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit

_PASSWORD = "correct horse battery staple"
_TIME_ZONE = "America/Bogota"


@pytest.fixture(autouse=True)
def _schema(_in_memory_database: None) -> Engine:
    # Explicitly depend on the conftest autouse fixture so it runs first: it sets
    # DATABASE_URL and clears the cached engine (mirrors test_auth_api.py).
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine


def _client() -> TestClient:
    # `set_session_cookie` sets `Secure`, so a plain `http://testserver` TestClient would
    # store the cookie but never resend it - `https://testserver` makes the round trip work.
    return TestClient(create_app(), base_url="https://testserver")


def _register(client: TestClient, *, email: str = "someone@example.com") -> TestClient:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": _PASSWORD, "time_zone": _TIME_ZONE},
    )
    return client


@pytest.fixture
def client() -> TestClient:
    return _register(_client())


def _create(client: TestClient, text: str):
    return client.post("/api/v1/tasks", json={"text": text})


def _list(client: TestClient, **params: object):
    return client.get("/api/v1/tasks", params=params)


def _delete(client: TestClient, task_id: object):
    # The CSRF guard requires `Content-Type: application/json` on every mutation, even
    # a body-less DELETE - a real browser's `fetch` would set it explicitly too.
    return client.delete(f"/api/v1/tasks/{task_id}", headers={"content-type": "application/json"})


def _user_id(client: TestClient) -> int:
    return client.get("/api/v1/auth/me").json()["id"]


def _seed_pomodoro(*, user_id: int, task_id: int) -> None:
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        session.add(
            tables.Pomodoro(
                user_id=user_id,
                task_id=task_id,
                started_at=now,
                ended_at=now,
                duration_seconds=1500,
                status="completed",
            )
        )
        session.commit()


class TestCreateTask:
    def test_creates_a_task_at_the_front_of_active(self, client: TestClient) -> None:
        _create(client, "First")

        response = _create(client, "Second")

        assert response.status_code == 201
        body = response.json()
        assert body["text"] == "Second"
        assert body["status"] == "active"
        assert body["archived_at"] is None
        assert body["deletable"] is True
        assert body["tag_ids"] == []

        items = _list(client).json()["items"]
        assert [task["text"] for task in items] == ["Second", "First"]

    def test_rejects_empty_text(self, client: TestClient) -> None:
        response = _create(client, "   ")

        assert response.status_code == 400

    def test_rejects_text_over_200_characters(self, client: TestClient) -> None:
        response = _create(client, "x" * 201)

        assert response.status_code == 400

    def test_rejects_a_duplicate_active_text_case_and_space_insensitive(
        self, client: TestClient
    ) -> None:
        _create(client, "Write the report")

        response = _create(client, " write the report ")

        assert response.status_code == 400

    def test_create_without_a_session_is_rejected(self) -> None:
        response = _create(_client(), "Write")

        assert response.status_code == 401


class TestListTasks:
    def test_lists_active_tasks_front_to_back(self, client: TestClient) -> None:
        _create(client, "A")
        _create(client, "B")

        response = _list(client, status="active")

        assert response.status_code == 200
        body = response.json()
        assert [task["text"] for task in body["items"]] == ["B", "A"]
        assert body["active_count"] == 2
        assert body["archived_count"] == 0

    def test_filters_by_name_query_substring_case_insensitive(self, client: TestClient) -> None:
        _create(client, "Write the report")
        _create(client, "Buy milk")

        response = _list(client, name_query="REPORT")

        assert [task["text"] for task in response.json()["items"]] == ["Write the report"]

    def test_the_no_tag_sentinel_matches_tasks_with_no_tag(self, client: TestClient) -> None:
        _create(client, "Untagged")

        response = _list(client, no_tag="true")

        assert [task["text"] for task in response.json()["items"]] == ["Untagged"]

    def test_an_unknown_tag_id_narrows_to_empty_never_falls_back_to_unrestricted(
        self, client: TestClient
    ) -> None:
        _create(client, "Untagged")

        response = _list(client, tag_ids=[999])

        assert response.json()["items"] == []

    def test_counts_reflect_totals_regardless_of_the_active_filter(
        self, client: TestClient
    ) -> None:
        _create(client, "Keep me")

        response = _list(client, name_query="nothing matches this")

        body = response.json()
        assert body["items"] == []
        assert body["active_count"] == 1
        assert body["archived_count"] == 0

    def test_list_without_a_session_is_rejected(self) -> None:
        response = _list(_client())

        assert response.status_code == 401


class TestEditTaskText:
    def test_edits_the_text(self, client: TestClient) -> None:
        created = _create(client, "Old").json()

        response = client.put(f"/api/v1/tasks/{created['id']}", json={"text": "New"})

        assert response.status_code == 200
        assert response.json()["text"] == "New"

    def test_rejects_empty_text(self, client: TestClient) -> None:
        created = _create(client, "Old").json()

        response = client.put(f"/api/v1/tasks/{created['id']}", json={"text": "   "})

        assert response.status_code == 400

    def test_rejects_a_collision_with_another_active_task(self, client: TestClient) -> None:
        _create(client, "Trabajo")
        other = _create(client, "Other").json()

        response = client.put(f"/api/v1/tasks/{other['id']}", json={"text": "trabajo"})

        assert response.status_code == 400

    def test_editing_an_unknown_task_is_a_404(self, client: TestClient) -> None:
        response = client.put("/api/v1/tasks/999999", json={"text": "New"})

        assert response.status_code == 404

    def test_edit_without_a_session_is_rejected(self, client: TestClient) -> None:
        created = _create(client, "Old").json()

        response = _client().put(f"/api/v1/tasks/{created['id']}", json={"text": "New"})

        assert response.status_code == 401


class TestDeleteTask:
    def test_deletes_a_task_with_no_pomodoros(self, client: TestClient) -> None:
        created = _create(client, "Throwaway").json()

        response = _delete(client, created["id"])

        assert response.status_code == 204
        assert _list(client).json()["items"] == []

    def test_rejects_deleting_a_task_with_a_recorded_pomodoro(self, client: TestClient) -> None:
        created = _create(client, "Worked on").json()
        _seed_pomodoro(user_id=_user_id(client), task_id=created["id"])

        response = _delete(client, created["id"])

        assert response.status_code == 400
        items = _list(client).json()["items"]
        assert items[0]["deletable"] is False

    def test_deleting_an_unknown_task_is_a_404(self, client: TestClient) -> None:
        response = _delete(client, 999999)

        assert response.status_code == 404

    def test_delete_without_a_session_is_rejected(self, client: TestClient) -> None:
        created = _create(client, "Keep").json()

        response = _delete(_client(), created["id"])

        assert response.status_code == 401


class TestCrossUserIsolation:
    def test_user_b_never_sees_user_as_tasks_in_list(self) -> None:
        user_a = _register(_client(), email="a@example.com")
        _create(user_a, "A's task")
        user_b = _register(_client(), email="b@example.com")

        body = _list(user_b).json()

        assert body["items"] == []
        assert body["active_count"] == 0

    def test_user_b_cannot_edit_user_as_task(self) -> None:
        user_a = _register(_client(), email="a@example.com")
        task = _create(user_a, "A's task").json()
        user_b = _register(_client(), email="b@example.com")

        response = user_b.put(f"/api/v1/tasks/{task['id']}", json={"text": "hijacked"})

        assert response.status_code == 404
        assert _list(user_a).json()["items"][0]["text"] == "A's task"

    def test_user_b_cannot_delete_user_as_task(self) -> None:
        user_a = _register(_client(), email="a@example.com")
        task = _create(user_a, "A's task").json()
        user_b = _register(_client(), email="b@example.com")

        response = _delete(user_b, task["id"])

        assert response.status_code == 404
        assert len(_list(user_a).json()["items"]) == 1

    def test_user_b_creating_the_same_text_as_user_a_never_collides(self) -> None:
        user_a = _register(_client(), email="a@example.com")
        _create(user_a, "Shared text")
        user_b = _register(_client(), email="b@example.com")

        response = _create(user_b, "Shared text")

        assert response.status_code == 201


class TestCsrfGuard:
    def test_a_mutation_without_json_content_type_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/tasks",
            data="text=x",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 403
