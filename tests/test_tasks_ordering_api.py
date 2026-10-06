"""HTTP-level tests for the Tasks ordering & archive lifecycle API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.conftest import AuthedSession as _AuthedSession
from tests.conftest import FakeClock
from tests.conftest import as_other_user as _as_other_user
from tests.conftest import authed_session as _authed_session
from tests.conftest import build_tasks_client as _build_client
from tests.conftest import http_test_engine as _engine

if TYPE_CHECKING:
    from pathlib import Path

JSON_HEADERS = {"content-type": "application/json"}


def _create(s: _AuthedSession, text: str) -> Any:
    response = s.client.post("/api/tasks", cookies=s.cookies, json={"text": text})
    assert response.status_code == 201
    return response.json()


def _list_active(s: _AuthedSession) -> list[dict]:
    response = s.client.get("/api/tasks/active", cookies=s.cookies)
    assert response.status_code == 200
    return response.json()


def _list_archived(s: _AuthedSession) -> list[dict]:
    response = s.client.get("/api/tasks/archived", cookies=s.cookies)
    assert response.status_code == 200
    return response.json()


def _reorder(s: _AuthedSession, task_ids: list[int]) -> Any:
    return s.client.post(
        "/api/tasks/reorder", cookies=s.cookies, json={"task_ids": task_ids}, headers=JSON_HEADERS
    )


def _archive(s: _AuthedSession, task_id: int) -> Any:
    return s.client.post(f"/api/tasks/{task_id}/archive", cookies=s.cookies, headers=JSON_HEADERS)


def _unarchive(s: _AuthedSession, task_id: int) -> Any:
    return s.client.post(f"/api/tasks/{task_id}/unarchive", cookies=s.cookies, headers=JSON_HEADERS)


def _summary(s: _AuthedSession) -> Any:
    response = s.client.get("/api/tasks/summary", cookies=s.cookies)
    assert response.status_code == 200
    return response.json()


# --- reorder -----------------------------------------------------------------------------


@pytest.mark.unit
def test_reorder_persists_across_a_simulated_reload(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create(s, "first")
    second = _create(s, "second")
    third = _create(s, "third")
    # Newest-first on create: [third, second, first].
    new_order = [first["id"], third["id"], second["id"]]

    response = _reorder(s, new_order)
    assert response.status_code == 200
    assert [task["id"] for task in response.json()] == new_order

    # Re-fetch ("reload") and compare: the new order must have been persisted,
    # not merely echoed back in the response.
    reloaded_ids = [task["id"] for task in _list_active(s)]
    assert reloaded_ids == new_order


@pytest.mark.unit
def test_reorder_rejects_a_list_that_does_not_match_the_active_set(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create(s, "first")
    _create(s, "second")

    # Missing one id entirely.
    response = _reorder(s, [first["id"]])

    assert response.status_code == 409
    # The persisted order must be untouched by the rejected request.
    assert len(_list_active(s)) == 2


@pytest.mark.unit
def test_reorder_rejects_an_id_not_belonging_to_the_user(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create(s, "first")
    second = _create(s, "second")
    other_client, other_cookies = _as_other_user(s)
    foreign = other_client.post("/api/tasks", cookies=other_cookies, json={"text": "foreign"})
    assert foreign.status_code == 201

    response = _reorder(s, [first["id"], second["id"], foreign.json()["id"]])

    assert response.status_code == 409


@pytest.mark.unit
def test_reorder_requires_a_valid_session(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = client.post("/api/tasks/reorder", json={"task_ids": []}, headers=JSON_HEADERS)

    assert response.status_code == 401


# --- archive -----------------------------------------------------------------------------


@pytest.mark.unit
def test_archive_freezes_position_and_moves_to_archived_tab(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    original_position = task["position"]

    response = _archive(s, task["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["position"] == original_position
    assert body["archived_at"] is not None

    assert _list_active(s) == []
    archived_ids = [t["id"] for t in _list_archived(s)]
    assert archived_ids == [task["id"]]


@pytest.mark.unit
def test_archive_rejects_task_belonging_to_another_user(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    other_client, other_cookies = _as_other_user(s)

    response = other_client.post(
        f"/api/tasks/{task['id']}/archive", cookies=other_cookies, headers=JSON_HEADERS
    )

    assert response.status_code == 404
    assert _list_active(s)[0]["id"] == task["id"]


# --- unarchive ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unarchive_clears_archived_at_and_appends_to_end_of_active(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create(s, "first")
    second = _create(s, "second")
    archived = _archive(s, first["id"]).json()
    assert archived["archived_at"] is not None

    response = _unarchive(s, first["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["archived_at"] is None

    active_ids = [t["id"] for t in _list_active(s)]
    # `second` was already Active; the unarchived Task joins at the end.
    assert active_ids == [second["id"], first["id"]]


@pytest.mark.unit
def test_unarchive_rejects_text_collision_with_an_active_task(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task = _create(s, "write report")
    _archive(s, task["id"])
    _create(s, "write report")

    response = _unarchive(s, task["id"])

    assert response.status_code == 409
    # Still archived: the rejected unarchive must not have mutated the Task.
    assert _list_archived(s)[0]["id"] == task["id"]


@pytest.mark.unit
def test_archive_then_unarchive_ordering_is_archived_at_descending(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create(s, "first")
    second = _create(s, "second")
    s.clock.advance(60)
    _archive(s, first["id"])
    s.clock.advance(60)
    _archive(s, second["id"])

    archived_ids = [t["id"] for t in _list_archived(s)]

    # Most recently archived first: `second` was archived after `first`.
    assert archived_ids == [second["id"], first["id"]]


# --- tab counts --------------------------------------------------------------------------


@pytest.mark.unit
def test_summary_reports_active_and_archived_counts(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    first = _create(s, "first")
    _create(s, "second")
    _archive(s, first["id"])

    summary = _summary(s)

    assert summary == {"active": 1, "archived": 1}


@pytest.mark.unit
def test_summary_requires_a_valid_session(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    assert client.get("/api/tasks/summary").status_code == 401
