"""Tests for the T11 `api/v1/tasks` lifecycle endpoints: reorder, archive, unarchive.

Drives the real app (`entrypoints.app.create_app`) through `TestClient` over an
in-memory SQLite database (the `_in_memory_database` conftest fixture), never a
mocked repository - matching T10's existing `api/v1` test style.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from pomodoro.database.tables import SQLModel
from pomodoro.entrypoints.app import create_app
from pomodoro.entrypoints.dependencies import get_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit

_PASSWORD = "correct horse battery staple"
_TIME_ZONE = "America/Bogota"
_JSON_CONTENT_TYPE = {"content-type": "application/json"}


@pytest.fixture(autouse=True)
def _schema(_in_memory_database: None) -> Engine:
    # Explicitly depend on the conftest autouse fixture so it runs first: it sets
    # DATABASE_URL and clears the cached engine (mirrors test_tasks_api.py).
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


def _reorder(client: TestClient, task_ids: list[int]):
    return client.post("/api/v1/tasks/reorder", json={"task_ids": task_ids})


def _archive(client: TestClient, task_id: object):
    return client.post(f"/api/v1/tasks/{task_id}/archive", headers=_JSON_CONTENT_TYPE)


def _unarchive(client: TestClient, task_id: object):
    return client.post(f"/api/v1/tasks/{task_id}/unarchive", headers=_JSON_CONTENT_TYPE)


class TestReorder:
    def test_reorder_persists_the_new_order_across_a_simulated_reload(
        self, client: TestClient
    ) -> None:
        first = _create(client, "First").json()
        second = _create(client, "Second").json()
        third = _create(client, "Third").json()
        # Created newest-first: Third, Second, First.

        response = _reorder(client, [first["id"], second["id"], third["id"]])

        assert response.status_code == 200
        assert [task["text"] for task in response.json()] == ["First", "Second", "Third"]

        # A fresh list call simulates a reload reading the persisted positions back.
        reloaded = _list(client).json()["items"]
        assert [task["text"] for task in reloaded] == ["First", "Second", "Third"]

    def test_rejects_a_list_missing_one_of_the_active_ids(self, client: TestClient) -> None:
        first = _create(client, "First").json()
        _create(client, "Second")

        response = _reorder(client, [first["id"]])

        assert response.status_code == 400
        reloaded = _list(client).json()["items"]
        assert [task["text"] for task in reloaded] == ["Second", "First"]

    def test_rejects_a_list_with_an_id_outside_the_active_set(self, client: TestClient) -> None:
        first = _create(client, "First").json()
        second = _create(client, "Second").json()

        response = _reorder(client, [first["id"], second["id"], 999999])

        assert response.status_code == 400

    def test_rejects_a_list_that_repeats_an_id(self, client: TestClient) -> None:
        first = _create(client, "First").json()
        _create(client, "Second")

        response = _reorder(client, [first["id"], first["id"]])

        assert response.status_code == 400
        reloaded = _list(client).json()["items"]
        assert [task["text"] for task in reloaded] == ["Second", "First"]

    def test_does_not_apply_an_archived_tasks_id(self, client: TestClient) -> None:
        active = _create(client, "Active").json()
        archived = _create(client, "Archived").json()
        _archive(client, archived["id"])

        response = _reorder(client, [archived["id"], active["id"]])

        assert response.status_code == 400

    def test_reorder_without_a_session_is_rejected(self) -> None:
        response = _reorder(_client(), [1, 2])

        assert response.status_code == 401


class TestArchive:
    def test_archive_sets_archived_at_and_freezes_position(self, client: TestClient) -> None:
        created = _create(client, "Done with this").json()

        response = _archive(client, created["id"])

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "archived"
        assert body["archived_at"] is not None
        assert body["position"] == created["position"]

        active_items = _list(client, status="active").json()["items"]
        assert active_items == []
        archived_items = _list(client, status="archived").json()["items"]
        assert [task["text"] for task in archived_items] == ["Done with this"]

    def test_archiving_an_unknown_task_is_a_404(self, client: TestClient) -> None:
        response = _archive(client, 999999)

        assert response.status_code == 404

    def test_archive_without_a_session_is_rejected(self, client: TestClient) -> None:
        created = _create(client, "Keep").json()

        response = _archive(_client(), created["id"])

        assert response.status_code == 401


class TestUnarchive:
    def test_unarchive_clears_archived_at_and_appends_to_the_end(self, client: TestClient) -> None:
        archived = _create(client, "Was archived").json()
        _archive(client, archived["id"])
        _create(client, "Stays active")

        response = _unarchive(client, archived["id"])

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["archived_at"] is None

        active_items = _list(client, status="active").json()["items"]
        assert [task["text"] for task in active_items] == ["Stays active", "Was archived"]

    def test_unarchive_collision_with_an_active_task_is_rejected_with_a_clear_message(
        self, client: TestClient
    ) -> None:
        archived = _create(client, "Trabajo").json()
        _archive(client, archived["id"])
        _create(client, "Trabajo")

        response = _unarchive(client, archived["id"])

        assert response.status_code == 400
        assert "Trabajo" in response.json()["detail"]
        assert "unarchive" in response.json()["detail"].lower()

    def test_unarchiving_an_unknown_task_is_a_404(self, client: TestClient) -> None:
        response = _unarchive(client, 999999)

        assert response.status_code == 404

    def test_unarchive_without_a_session_is_rejected(self, client: TestClient) -> None:
        archived = _create(client, "Was archived").json()
        _archive(client, archived["id"])

        response = _unarchive(_client(), archived["id"])

        assert response.status_code == 401


class TestCrossUserIsolation:
    def test_user_b_cannot_reorder_user_as_tasks(self) -> None:
        user_a = _register(_client(), email="a@example.com")
        task = _create(user_a, "A's task").json()
        user_b = _register(_client(), email="b@example.com")

        response = _reorder(user_b, [task["id"]])

        assert response.status_code == 400

    def test_user_b_cannot_archive_user_as_task(self) -> None:
        user_a = _register(_client(), email="a@example.com")
        task = _create(user_a, "A's task").json()
        user_b = _register(_client(), email="b@example.com")

        response = _archive(user_b, task["id"])

        assert response.status_code == 404
        assert _list(user_a).json()["items"][0]["status"] == "active"
