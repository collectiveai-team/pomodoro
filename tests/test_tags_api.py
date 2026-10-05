"""HTTP-level tests for the Tags API: list, rename, delete.

Same `tmp_path`-backed SQLite setup as `test_tasks_api.py`: `TestClient`
dispatches on its own worker thread, so a `:memory:` database wouldn't be
visible across threads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.conftest import AuthedSession as _AuthedSession
from tests.conftest import as_other_user as _as_other_user
from tests.conftest import authed_session as _authed_session

if TYPE_CHECKING:
    from pathlib import Path


def _create_task(s: _AuthedSession, text: str, tags: list[str]) -> Any:
    response = s.client.post("/api/tasks", cookies=s.cookies, json={"text": text, "tags": tags})
    assert response.status_code == 201
    return response.json()


def _list_tags(s: _AuthedSession) -> list[dict]:
    response = s.client.get("/api/tags", cookies=s.cookies)
    assert response.status_code == 200
    return response.json()


def _tag_id_by_name(s: _AuthedSession, name: str) -> int:
    tag = next(t for t in _list_tags(s) if t["name"] == name)
    return tag["id"]


# --- list --------------------------------------------------------------------------------


@pytest.mark.unit
def test_list_tags_includes_orphaned(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create_task(s, "write report", ["work"])
    tag_id = _tag_id_by_name(s, "work")
    # Detach the Tag from every Task, orphaning it while it stays in the catalog.
    response = s.client.patch(f"/api/tasks/{task['id']}/tags", cookies=s.cookies, json={"tags": []})
    assert response.status_code == 200

    tags = _list_tags(s)

    assert [t["id"] for t in tags] == [tag_id]
    assert tags[0]["name"] == "work"


@pytest.mark.unit
def test_list_tags_requires_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.get("/api/tags")

    assert response.status_code == 401


@pytest.mark.unit
def test_list_tags_is_scoped_to_user(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create_task(s, "write report", ["work"])
    other_client, other_cookies = _as_other_user(s)

    response = other_client.get("/api/tags", cookies=other_cookies)

    assert response.status_code == 200
    assert response.json() == []


# --- rename --------------------------------------------------------------------------------


@pytest.mark.unit
def test_rename_tag_propagates_to_tasks_list(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create_task(s, "write report", ["work"])
    tag_id = _tag_id_by_name(s, "work")

    response = s.client.patch(f"/api/tags/{tag_id}", cookies=s.cookies, json={"name": "office"})

    assert response.status_code == 200
    assert response.json() == {"id": tag_id, "name": "office"}

    active = s.client.get("/api/tasks/active", cookies=s.cookies).json()
    assert active[0]["tags"] == ["office"]


@pytest.mark.unit
def test_rename_tag_rejects_duplicate_case_insensitive(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create_task(s, "write report", ["work"])
    _create_task(s, "buy groceries", ["home"])
    home_id = _tag_id_by_name(s, "home")

    response = s.client.patch(f"/api/tags/{home_id}", cookies=s.cookies, json={"name": "Work"})

    assert response.status_code == 409
    # Unrenamed: the Task's Tag is untouched.
    assert _tag_id_by_name(s, "home") == home_id


@pytest.mark.unit
def test_rename_tag_rejects_empty_name(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create_task(s, "write report", ["work"])
    tag_id = _tag_id_by_name(s, "work")

    response = s.client.patch(f"/api/tags/{tag_id}", cookies=s.cookies, json={"name": "   "})

    assert response.status_code == 422


@pytest.mark.unit
def test_rename_nonexistent_tag_404(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.patch("/api/tags/999999", cookies=s.cookies, json={"name": "office"})

    assert response.status_code == 404


@pytest.mark.unit
def test_rename_tag_cross_user_is_404(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create_task(s, "write report", ["work"])
    tag_id = _tag_id_by_name(s, "work")
    other_client, other_cookies = _as_other_user(s)

    response = other_client.patch(
        f"/api/tags/{tag_id}", cookies=other_cookies, json={"name": "office"}
    )

    assert response.status_code == 404
    # Untouched for the owner.
    assert _tag_id_by_name(s, "work") == tag_id


# --- delete --------------------------------------------------------------------------------


@pytest.mark.unit
def test_delete_tag_cascades_off_every_task(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create_task(s, "write report", ["work", "urgent"])
    second = _create_task(s, "review PR", ["work"])
    tag_id = _tag_id_by_name(s, "work")

    response = s.client.delete(
        f"/api/tags/{tag_id}", cookies=s.cookies, headers={"content-type": "application/json"}
    )

    assert response.status_code == 204
    active_tasks = s.client.get("/api/tasks/active", cookies=s.cookies).json()
    active = {task["id"]: task for task in active_tasks}
    assert active[first["id"]]["tags"] == ["urgent"]
    assert active[second["id"]]["tags"] == []
    assert all(t["id"] != tag_id for t in _list_tags(s))


@pytest.mark.unit
def test_delete_nonexistent_tag_404(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.delete(
        "/api/tags/999999", cookies=s.cookies, headers={"content-type": "application/json"}
    )

    assert response.status_code == 404


@pytest.mark.unit
def test_delete_tag_cross_user_is_404(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create_task(s, "write report", ["work"])
    tag_id = _tag_id_by_name(s, "work")
    other_client, other_cookies = _as_other_user(s)

    response = other_client.delete(
        f"/api/tags/{tag_id}",
        cookies=other_cookies,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 404
    assert _tag_id_by_name(s, "work") == tag_id
