"""HTTP-level tests for the Tasks API: list/filter, create, edit, delete.

Same `tmp_path`-backed SQLite setup as `test_auth_api.py`: `TestClient`
dispatches on its own worker thread, so a `:memory:` database wouldn't be
visible across threads.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pomodoro.api import session
from pomodoro.database import tables
from pomodoro.database.engine import session_scope
from pomodoro.database.tables import Pomodoro as PomodoroRow

from tests.conftest import NOW, TEST_PASSWORD, FakeClock
from tests.conftest import AuthedSession as _AuthedSession
from tests.conftest import as_other_user as _as_other_user
from tests.conftest import authed_session as _authed_session
from tests.conftest import build_tasks_client as _build_client
from tests.conftest import http_test_engine as _engine

if TYPE_CHECKING:
    from pathlib import Path


def _create(s: _AuthedSession, text: str, tags: list[str] | None = None) -> Any:
    body: dict[str, Any] = {"text": text}
    if tags is not None:
        body["tags"] = tags
    response = s.client.post("/api/tasks", cookies=s.cookies, json=body)
    assert response.status_code == 201
    return response.json()


def _list_active(s: _AuthedSession, **params) -> list[dict]:
    response = s.client.get("/api/tasks/active", cookies=s.cookies, params=params)
    assert response.status_code == 200
    return response.json()


def _list_archived(s: _AuthedSession, **params) -> list[dict]:
    response = s.client.get("/api/tasks/archived", cookies=s.cookies, params=params)
    assert response.status_code == 200
    return response.json()


def _seed_completed_pomodoro(s: _AuthedSession, task_id: int) -> None:
    """Record a completed Pomodoro directly at the storage level (T12 owns the Timer API)."""
    with session_scope(s.engine) as db:
        db.add(
            PomodoroRow(
                user_id=s.user_id,
                task_id=task_id,
                started_at=NOW,
                ended_at=NOW + timedelta(minutes=25),
                duration_seconds=1500,
                status="completed",
            )
        )
        db.commit()


# --- creation --------------------------------------------------------------------------


@pytest.mark.unit
def test_create_task_is_newest_first(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create(s, "write report")
    second = _create(s, "review PR")

    active = _list_active(s)

    assert [task["id"] for task in active] == [second["id"], first["id"]]
    assert active[0]["deletable"] is True


@pytest.mark.unit
def test_create_task_rejects_empty_text(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.post("/api/tasks", cookies=s.cookies, json={"text": "   "})

    assert response.status_code == 422


@pytest.mark.unit
def test_create_task_rejects_duplicate_text_among_active_only(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create(s, "write report")

    response = s.client.post("/api/tasks", cookies=s.cookies, json={"text": "Write Report"})

    assert response.status_code == 409


@pytest.mark.unit
def test_create_task_allows_text_matching_an_archived_task(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    archived = _create(s, "write report")
    # Archiving is T10's endpoint; flip `archived_at` directly at the storage
    # level so this test only exercises T9's archived/active asymmetry rule.
    with session_scope(s.engine) as db:
        row = db.get(tables.Task, archived["id"])
        assert row is not None
        row.archived_at = NOW
        db.add(row)
        db.commit()

    response = s.client.post("/api/tasks", cookies=s.cookies, json={"text": "write report"})

    assert response.status_code == 201


@pytest.mark.unit
def test_create_task_assigns_tags_by_name_creating_or_reusing(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    first = _create(s, "write report", tags=["Work", "urgent"])
    second = _create(s, "review PR", tags=["work"])

    assert set(first["tags"]) == {"Work", "urgent"}
    assert second["tags"] == ["Work"]


# --- filtering ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_by_text_and_tags(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    _create(s, "write report", tags=["work"])
    _create(s, "buy groceries")
    _create(s, "write poem")

    by_text = _list_active(s, text="write")
    assert {task["text"] for task in by_text} == {"write report", "write poem"}

    by_tag = _list_active(s, tags=["work"])
    assert [task["text"] for task in by_tag] == ["write report"]

    untagged = _list_active(s, tags=["sin etiqueta"])
    assert {task["text"] for task in untagged} == {"buy groceries", "write poem"}

    combined = _list_active(s, text="write", tags=["work"])
    assert [task["text"] for task in combined] == ["write report"]


# --- edit --------------------------------------------------------------------------------


@pytest.mark.unit
def test_edit_text_applies_create_validation(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    _create(s, "review PR")

    empty_response = s.client.patch(
        f"/api/tasks/{task['id']}/text", cookies=s.cookies, json={"text": "  "}
    )
    assert empty_response.status_code == 422

    collision_response = s.client.patch(
        f"/api/tasks/{task['id']}/text", cookies=s.cookies, json={"text": "review PR"}
    )
    assert collision_response.status_code == 409

    ok_response = s.client.patch(
        f"/api/tasks/{task['id']}/text", cookies=s.cookies, json={"text": "write the report"}
    )
    assert ok_response.status_code == 200
    assert ok_response.json()["text"] == "write the report"


@pytest.mark.unit
def test_edit_tags_replaces_the_full_set(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report", tags=["work"])

    response = s.client.patch(
        f"/api/tasks/{task['id']}/tags", cookies=s.cookies, json={"tags": ["urgent", "home"]}
    )

    assert response.status_code == 200
    assert set(response.json()["tags"]) == {"urgent", "home"}


@pytest.mark.unit
def test_edit_rejects_task_belonging_to_another_user(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    other_client, other_cookies = _as_other_user(s)

    response = other_client.patch(
        f"/api/tasks/{task['id']}/text", cookies=other_cookies, json={"text": "stolen"}
    )

    assert response.status_code == 404


# --- deletable flag + delete ---------------------------------------------------------------


@pytest.mark.unit
def test_deletable_flag_is_false_once_a_pomodoro_is_recorded(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    assert task["deletable"] is True

    _seed_completed_pomodoro(s, task["id"])

    active = _list_active(s)
    assert active[0]["deletable"] is False


@pytest.mark.unit
def test_delete_succeeds_when_deletable(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")

    response = s.client.delete(
        f"/api/tasks/{task['id']}", cookies=s.cookies, headers={"content-type": "application/json"}
    )

    assert response.status_code == 204
    assert _list_active(s) == []


@pytest.mark.unit
def test_delete_rejects_when_not_deletable(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    _seed_completed_pomodoro(s, task["id"])

    response = s.client.delete(
        f"/api/tasks/{task['id']}", cookies=s.cookies, headers={"content-type": "application/json"}
    )

    assert response.status_code == 409


@pytest.mark.unit
def test_delete_rejects_task_belonging_to_another_user(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    other_client, other_cookies = _as_other_user(s)

    response = other_client.delete(
        f"/api/tasks/{task['id']}",
        cookies=other_cookies,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 404
    assert _list_active(s)[0]["id"] == task["id"]


# --- cross-user isolation -----------------------------------------------------------------


@pytest.mark.unit
def test_tasks_are_isolated_per_user(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    clock = FakeClock()
    client = _build_client(engine, clock)
    register_a = client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": TEST_PASSWORD, "time_zone": "UTC"},
    )
    register_b = client.post(
        "/api/auth/register",
        json={"email": "b@example.com", "password": TEST_PASSWORD, "time_zone": "UTC"},
    )
    cookies_a = {session.SESSION_COOKIE_NAME: register_a.cookies[session.SESSION_COOKIE_NAME]}
    cookies_b = {session.SESSION_COOKIE_NAME: register_b.cookies[session.SESSION_COOKIE_NAME]}

    client.post("/api/tasks", cookies=cookies_a, json={"text": "a's task"})
    client.post("/api/tasks", cookies=cookies_b, json={"text": "b's task"})

    active_a = client.get("/api/tasks/active", cookies=cookies_a).json()
    active_b = client.get("/api/tasks/active", cookies=cookies_b).json()

    assert [task["text"] for task in active_a] == ["a's task"]
    assert [task["text"] for task in active_b] == ["b's task"]


@pytest.mark.unit
def test_list_requires_a_valid_session(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    assert client.get("/api/tasks/active").status_code == 401
    assert client.get("/api/tasks/archived").status_code == 401
