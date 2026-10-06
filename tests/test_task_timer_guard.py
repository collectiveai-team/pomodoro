"""HTTP-level tests for the Task/Timer interaction guard (user story #31).

A Task currently referenced by the User's Timer (any non-Idle phase) can be
neither archived nor permanently deleted, and the `deletable` flag reflects
that even when the Task has zero Pomodoros recorded. Same `tmp_path`-backed
SQLite setup as `test_tasks_api.py`/`test_timer_api.py`, built on the shared
`tests.conftest` client/session helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.conftest import AuthedSession as _AuthedSession
from tests.conftest import authed_session as _authed_session
from tests.conftest import create_task as _create_task

if TYPE_CHECKING:
    from pathlib import Path


def _start(s: _AuthedSession, task_id: int) -> Any:
    return s.client.post("/api/timer/start", cookies=s.cookies, json={"task_id": task_id})


def _action(s: _AuthedSession, path: str) -> Any:
    return s.client.post(f"/api/timer/{path}", cookies=s.cookies, json={})


def _archive(s: _AuthedSession, task_id: int) -> Any:
    return s.client.post(f"/api/tasks/{task_id}/archive", cookies=s.cookies, json={})


def _delete(s: _AuthedSession, task_id: int) -> Any:
    return s.client.delete(
        f"/api/tasks/{task_id}", cookies=s.cookies, headers={"content-type": "application/json"}
    )


def _active(s: _AuthedSession) -> list[dict]:
    response = s.client.get("/api/tasks/active", cookies=s.cookies)
    assert response.status_code == 200
    return response.json()


def _started_then_stopped(s: _AuthedSession) -> int:
    """Create a Task, start a Pomodoro on it, then stop into AskingToLog."""
    task_id = _create_task(s, "write report")
    _start(s, task_id)
    s.clock.advance(60)
    assert _action(s, "stop").json()["phase"] == "asking_to_log"
    return task_id


@pytest.mark.unit
def test_archive_rejected_while_timer_is_running_on_the_task(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    assert _start(s, task_id).status_code == 200

    response = _archive(s, task_id)

    assert response.status_code == 409
    assert _active(s)[0]["archived_at"] is None


@pytest.mark.unit
def test_delete_rejected_while_timer_is_running_on_the_task(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    assert _start(s, task_id).status_code == 200

    response = _delete(s, task_id)

    assert response.status_code == 409
    assert _active(s)[0]["id"] == task_id


@pytest.mark.unit
def test_deletable_flag_is_false_while_in_progress_even_with_zero_pomodoros(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    assert _active(s)[0]["deletable"] is True

    assert _start(s, task_id).status_code == 200

    assert _active(s)[0]["deletable"] is False


@pytest.mark.unit
def test_archive_and_delete_rejected_while_paused_and_while_on_break(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    _start(s, task_id)

    _action(s, "pause")
    assert _archive(s, task_id).status_code == 409
    assert _delete(s, task_id).status_code == 409

    _action(s, "resume")
    s.clock.advance(1500)  # complete the Pomodoro -> ReadyForNext, same task
    assert _archive(s, task_id).status_code == 409

    _action(s, "start-break")
    assert _archive(s, task_id).status_code == 409
    assert _delete(s, task_id).status_code == 409


@pytest.mark.unit
def test_archive_allowed_again_after_stop_then_log(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _started_then_stopped(s)
    assert _archive(s, task_id).status_code == 409  # still in progress: AskingToLog

    # Logging persists an interrupted Pomodoro, which separately (T9) makes
    # the Task non-deletable by pomodoro count -- irrelevant to this guard,
    # so only archive (unaffected by that rule) is exercised here.
    assert _action(s, "log").json()["phase"] == "idle"

    assert _archive(s, task_id).status_code == 200


@pytest.mark.unit
def test_delete_allowed_again_after_stop_then_discard(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _started_then_stopped(s)

    # Discarding persists nothing, so the Task carries zero Pomodoros
    # afterwards and both actions become allowed again.
    assert _action(s, "discard").json()["phase"] == "idle"

    assert _delete(s, task_id).status_code == 204


@pytest.mark.unit
def test_archive_allowed_again_after_stop_then_discard(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    _start(s, task_id)
    s.clock.advance(60)
    _action(s, "stop")

    _action(s, "discard")

    assert _archive(s, task_id).status_code == 200


@pytest.mark.unit
def test_a_different_task_is_unaffected_by_the_in_progress_guard(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    in_progress_id = _create_task(s, "write report")
    other_id = _create_task(s, "read book")
    _start(s, in_progress_id)

    assert _archive(s, other_id).status_code == 200
    assert _delete(s, other_id).status_code == 204
