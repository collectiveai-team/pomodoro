"""Tests for the T12 `api/v1/tags` router: list, rename, delete the catalog.

Drives the real app (`entrypoints.app.create_app`) through `TestClient` over an
in-memory SQLite database (the `_in_memory_database` conftest fixture), never a
mocked repository - matching T10/T11's existing `api/v1` test style. Creating a
Tag and assigning it to a Task is out of this ticket's scope (no endpoint
exists yet), so tests seed both directly via a `Session`, mirroring
`test_tasks_api.py`'s `_seed_pomodoro` helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlmodel import Session, select

from pomodoro.database import tables
from pomodoro.entrypoints.dependencies import get_engine

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("_schema")]


def _list_tags(client: TestClient):
    return client.get("/api/v1/tags")


def _rename(client: TestClient, tag_id: object, name: str):
    return client.put(f"/api/v1/tags/{tag_id}", json={"name": name})


def _delete(client: TestClient, tag_id: object):
    # The CSRF guard requires `Content-Type: application/json` on every mutation, even
    # a body-less DELETE - a real browser's `fetch` would set it explicitly too.
    return client.delete(f"/api/v1/tags/{tag_id}", headers={"content-type": "application/json"})


def _user_id(client: TestClient) -> int:
    return client.get("/api/v1/auth/me").json()["id"]


def _create_task(client: TestClient, text: str) -> int:
    return client.post("/api/v1/tasks", json={"text": text}).json()["id"]


def _seed_tag(*, user_id: int, name: str) -> int:
    with Session(get_engine()) as session:
        row = tables.Tag(user_id=user_id, name=name, name_key=name.strip().casefold())
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def _assign_tag(*, task_id: int, tag_id: int) -> None:
    with Session(get_engine()) as session:
        session.add(tables.TaskTags(task_id=task_id, tag_id=tag_id))
        session.commit()


def _task_tags_rows_for(tag_id: int) -> list[tables.TaskTags]:
    with Session(get_engine()) as session:
        return list(session.exec(select(tables.TaskTags).where(tables.TaskTags.tag_id == tag_id)))


class TestListTags:
    def test_lists_a_tag_with_zero_tasks(self, client: TestClient) -> None:
        _seed_tag(user_id=_user_id(client), name="Trabajo")

        response = _list_tags(client)

        assert response.status_code == 200
        assert [tag["name"] for tag in response.json()] == ["Trabajo"]

    def test_list_without_a_session_is_rejected(self, anonymous_client: TestClient) -> None:
        response = _list_tags(anonymous_client)

        assert response.status_code == 401


class TestRenameTag:
    def test_renames_and_is_visible_immediately_on_every_task_that_carries_it(
        self, client: TestClient
    ) -> None:
        task_id = _create_task(client, "Write the report")
        tag_id = _seed_tag(user_id=_user_id(client), name="Trabajo")
        _assign_tag(task_id=task_id, tag_id=tag_id)

        response = _rename(client, tag_id, "Oficina")

        assert response.status_code == 200
        assert response.json()["name"] == "Oficina"
        assert [tag["name"] for tag in _list_tags(client).json()] == ["Oficina"]
        task = client.get("/api/v1/tasks").json()["items"][0]
        assert task["tag_ids"] == [tag_id]

    def test_rejects_a_normalized_duplicate_name(self, client: TestClient) -> None:
        user_id = _user_id(client)
        _seed_tag(user_id=user_id, name="Oficina")
        tag_id = _seed_tag(user_id=user_id, name="Trabajo")

        response = _rename(client, tag_id, " oficina ")

        assert response.status_code == 400
        assert [tag["name"] for tag in _list_tags(client).json()] == ["Oficina", "Trabajo"]

    def test_renaming_to_its_own_current_name_is_not_a_collision(self, client: TestClient) -> None:
        tag_id = _seed_tag(user_id=_user_id(client), name="Trabajo")

        response = _rename(client, tag_id, "Trabajo")

        assert response.status_code == 200

    def test_renaming_an_unknown_tag_is_a_404(self, client: TestClient) -> None:
        response = _rename(client, 999999, "New name")

        assert response.status_code == 404

    def test_rename_without_a_session_is_rejected(
        self, client: TestClient, anonymous_client: TestClient
    ) -> None:
        tag_id = _seed_tag(user_id=_user_id(client), name="Trabajo")

        response = _rename(anonymous_client, tag_id, "Oficina")

        assert response.status_code == 401


class TestDeleteTag:
    def test_deletes_and_cascades_removal_from_every_task_leaving_no_dangling_reference(
        self, client: TestClient
    ) -> None:
        task_id = _create_task(client, "Write the report")
        tag_id = _seed_tag(user_id=_user_id(client), name="Trabajo")
        _assign_tag(task_id=task_id, tag_id=tag_id)

        response = _delete(client, tag_id)

        assert response.status_code == 204
        assert _list_tags(client).json() == []
        assert _task_tags_rows_for(tag_id) == []
        task = client.get("/api/v1/tasks").json()["items"][0]
        assert task["tag_ids"] == []

    def test_deleting_an_unknown_tag_is_a_404(self, client: TestClient) -> None:
        response = _delete(client, 999999)

        assert response.status_code == 404

    def test_delete_without_a_session_is_rejected(
        self, client: TestClient, anonymous_client: TestClient
    ) -> None:
        tag_id = _seed_tag(user_id=_user_id(client), name="Trabajo")

        response = _delete(anonymous_client, tag_id)

        assert response.status_code == 401


class TestCrossUserIsolation:
    def test_two_users_can_hold_a_same_named_tag_without_collision(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        user_a = make_client(email="a@example.com")
        user_b = make_client(email="b@example.com")
        _seed_tag(user_id=_user_id(user_a), name="Trabajo")

        # The per-User unique constraint on (user_id, name_key) would raise at commit
        # time here if Tag uniqueness were accidentally global rather than per-User.
        _seed_tag(user_id=_user_id(user_b), name="Trabajo")

        assert [tag["name"] for tag in _list_tags(user_a).json()] == ["Trabajo"]
        assert [tag["name"] for tag in _list_tags(user_b).json()] == ["Trabajo"]

    def test_user_b_never_sees_user_as_tags_in_list(
        self, make_client: Callable[..., TestClient]
    ) -> None:
        user_a = make_client(email="a@example.com")
        _seed_tag(user_id=_user_id(user_a), name="A's tag")
        user_b = make_client(email="b@example.com")

        assert _list_tags(user_b).json() == []

    def test_user_b_cannot_rename_user_as_tag(self, make_client: Callable[..., TestClient]) -> None:
        user_a = make_client(email="a@example.com")
        tag_id = _seed_tag(user_id=_user_id(user_a), name="A's tag")
        user_b = make_client(email="b@example.com")

        response = _rename(user_b, tag_id, "hijacked")

        assert response.status_code == 404
        assert _list_tags(user_a).json()[0]["name"] == "A's tag"

    def test_user_b_cannot_delete_user_as_tag(self, make_client: Callable[..., TestClient]) -> None:
        user_a = make_client(email="a@example.com")
        tag_id = _seed_tag(user_id=_user_id(user_a), name="A's tag")
        user_b = make_client(email="b@example.com")

        response = _delete(user_b, tag_id)

        assert response.status_code == 404
        assert len(_list_tags(user_a).json()) == 1


class TestCsrfGuard:
    def test_a_mutation_without_json_content_type_is_rejected(self, client: TestClient) -> None:
        tag_id = _seed_tag(user_id=_user_id(client), name="Trabajo")

        response = client.put(
            f"/api/v1/tags/{tag_id}",
            data="name=x",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 403
