"""HTTP-level tests for the Timer API: get, every action, and day summary.

Same `tmp_path`-backed SQLite setup as `test_tasks_api.py`, built on the same
shared `tests.conftest` client/session helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.conftest import AuthedSession as _AuthedSession
from tests.conftest import FakeClock
from tests.conftest import as_other_user as _as_other_user
from tests.conftest import authed_session as _authed_session
from tests.conftest import build_tasks_client as _build_client
from tests.conftest import create_task as _create_task
from tests.conftest import http_test_engine as _engine

if TYPE_CHECKING:
    from pathlib import Path


def _get_timer(s: _AuthedSession) -> Any:
    response = s.client.get("/api/timer", cookies=s.cookies)
    assert response.status_code == 200
    return response.json()


def _action(s: _AuthedSession, path: str, body: dict[str, Any] | None = None) -> Any:
    return s.client.post(f"/api/timer/{path}", cookies=s.cookies, json=body or {})


def _summary(s: _AuthedSession) -> Any:
    response = s.client.get("/api/timer/summary", cookies=s.cookies)
    assert response.status_code == 200
    return response.json()


@pytest.mark.unit
def test_timer_requires_a_valid_session(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    assert client.get("/api/timer").status_code == 401
    assert client.get("/api/timer/summary").status_code == 401
    assert client.post("/api/timer/pause", json={}).status_code == 401


@pytest.mark.unit
def test_start_rejects_a_task_not_owned_by_the_caller(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    other_client, other_cookies = _as_other_user(s)
    other_task = other_client.post("/api/tasks", cookies=other_cookies, json={"text": "their task"})
    other_task_id = other_task.json()["id"]

    response = _action(s, "start", {"task_id": other_task_id})

    assert response.status_code == 404


@pytest.mark.unit
def test_start_rejects_an_archived_task(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    archive = s.client.post(f"/api/tasks/{task_id}/archive", cookies=s.cookies, json={})
    assert archive.status_code == 200

    response = _action(s, "start", {"task_id": task_id})

    assert response.status_code == 422


@pytest.mark.unit
def test_full_sequence_start_pause_resume_stop_log(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")

    start = _action(s, "start", {"task_id": task_id})
    assert start.status_code == 200
    assert start.json()["phase"] == "pomodoro_running"
    assert start.json()["task"] == {"id": task_id, "text": "write report"}
    assert start.json()["remaining_seconds"] == 1500

    s.clock.advance(60)
    pause = _action(s, "pause")
    assert pause.json()["phase"] == "pomodoro_paused"
    assert pause.json()["remaining_seconds"] == 1500 - 60

    s.clock.advance(300)  # paused time must not count toward active time
    resume = _action(s, "resume")
    assert resume.json()["phase"] == "pomodoro_running"
    assert resume.json()["remaining_seconds"] == 1500 - 60

    s.clock.advance(120)
    stop = _action(s, "stop")
    assert stop.json()["phase"] == "asking_to_log"

    log = _action(s, "log")
    assert log.status_code == 200
    assert log.json()["phase"] == "idle"
    assert log.json()["task"] is None

    # Interrupted Pomodoros never count toward the "completed today" summary.
    assert _summary(s)["completed_today"] == 0


@pytest.mark.unit
def test_stop_then_discard_leaves_no_trace(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    _action(s, "start", {"task_id": task_id})
    s.clock.advance(60)
    assert _action(s, "stop").json()["phase"] == "asking_to_log"

    discard = _action(s, "discard")
    assert discard.json()["phase"] == "idle"

    timer = _get_timer(s)
    assert timer["phase"] == "idle"
    assert timer["task"] is None
    assert _summary(s)["completed_today"] == 0


@pytest.mark.unit
def test_auto_completes_at_25_minutes_without_intermediate_calls(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    _action(s, "start", {"task_id": task_id})

    s.clock.advance(1500)  # jump straight to 25 active minutes, no requests in between
    timer = _get_timer(s)

    assert timer["phase"] == "ready_for_next"
    assert timer["task"]["id"] == task_id  # ReadyForNext still references the same Task

    summary = _summary(s)
    assert summary["completed_today"] == 1
    assert summary["until_long_break"] == 4


@pytest.mark.unit
def test_invalid_action_responds_409_with_current_timer(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    _action(s, "start", {"task_id": task_id})

    response = _action(s, "resume")  # only valid from Paused, not Running

    assert response.status_code == 409
    body = response.json()["detail"]
    assert body["phase"] == "pomodoro_running"
    assert body["task"]["id"] == task_id


@pytest.mark.unit
def test_next_pomodoro_continues_on_the_same_task(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    _action(s, "start", {"task_id": task_id})
    s.clock.advance(1500)
    assert _get_timer(s)["phase"] == "ready_for_next"

    again = _action(s, "next-pomodoro")

    assert again.status_code == 200
    assert again.json()["phase"] == "pomodoro_running"
    assert again.json()["task"]["id"] == task_id


@pytest.mark.unit
def test_break_elapses_on_its_own_while_app_is_closed(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")
    _action(s, "start", {"task_id": task_id})
    s.clock.advance(1500)
    assert _action(s, "start-break").json()["phase"] == "break_running"

    s.clock.advance(5 * 60)  # short Break's full duration, no intermediate calls
    timer = _get_timer(s)

    assert timer["phase"] == "idle"
    assert timer["task"] is None


@pytest.mark.unit
def test_break_cadence_is_long_on_every_fifth_completed_pomodoro(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    task_id = _create_task(s, "write report")

    break_kinds = []
    for _ in range(5):
        _action(s, "start", {"task_id": task_id})
        s.clock.advance(1500)
        break_kinds.append(_action(s, "start-break").json()["break_kind"])
        _action(s, "skip-break")

    assert break_kinds == ["short", "short", "short", "short", "long"]


@pytest.mark.unit
def test_day_summary_resets_at_local_midnight_not_utc_midnight(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="America/Argentina/Buenos_Aires")
    task_id = _create_task(s, "write report")

    _action(s, "start", {"task_id": task_id})
    # Completes at 2026-01-01T00:25:00Z == 2025-12-31T21:25:00-03:00 (still Dec 31 locally).
    s.clock.advance(1500)
    assert _summary(s)["completed_today"] == 1

    # Cross the local-day boundary (2026-01-01T03:00:00Z == local midnight) without
    # completing another Pomodoro: the earlier one no longer belongs to "today".
    s.clock.advance(3 * 3600)
    assert _summary(s)["completed_today"] == 0
