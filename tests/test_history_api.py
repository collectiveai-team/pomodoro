"""HTTP-level tests for the History API: monthly heatmap + day detail.

Same `tmp_path`-backed SQLite setup as `test_tasks_api.py`, built on the same
shared `tests.conftest` client/session helpers. Core aggregation rules
(midnight-crossing, time-zone handling, filtering) are already exhaustively
covered by `test_core_history.py`; these tests focus on HTTP wiring: query
params, session scoping, and per-User isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tests.conftest import AuthedSession as _AuthedSession
from tests.conftest import as_other_user as _as_other_user
from tests.conftest import authed_session as _authed_session
from tests.conftest import create_task as _create_task

if TYPE_CHECKING:
    from pathlib import Path


def _complete_pomodoro(s: _AuthedSession, task_id: int) -> None:
    """Start a Pomodoro on `task_id`, let it auto-complete, and return the Timer to Idle."""
    response = s.client.post("/api/timer/start", cookies=s.cookies, json={"task_id": task_id})
    assert response.status_code == 200
    s.clock.advance(1500)
    skip = s.client.post("/api/timer/skip-break", cookies=s.cookies, json={})
    assert skip.status_code == 200
    assert skip.json()["phase"] == "idle"


def _log_interrupted(s: _AuthedSession, task_id: int, seconds: int) -> None:
    """Start, advance by `seconds`, then stop+log an interrupted Pomodoro."""
    response = s.client.post("/api/timer/start", cookies=s.cookies, json={"task_id": task_id})
    assert response.status_code == 200
    s.clock.advance(seconds)
    assert s.client.post("/api/timer/stop", cookies=s.cookies, json={}).status_code == 200
    assert s.client.post("/api/timer/log", cookies=s.cookies, json={}).status_code == 200


def _month(s: _AuthedSession, year: int, month: int) -> Any:
    response = s.client.get(
        "/api/history/month", cookies=s.cookies, params={"year": year, "month": month}
    )
    assert response.status_code == 200
    return response.json()


def _day(s: _AuthedSession, iso_date: str, **params: Any) -> Any:
    response = s.client.get(
        "/api/history/day", cookies=s.cookies, params={"date": iso_date, **params}
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.unit
def test_month_heatmap_requires_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")

    response = s.client.get("/api/history/month", params={"year": 2026, "month": 1})

    assert response.status_code == 401


@pytest.mark.unit
def test_day_detail_requires_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")

    response = s.client.get("/api/history/day", params={"date": "2026-01-01"})

    assert response.status_code == 401


@pytest.mark.unit
def test_month_heatmap_rejects_an_out_of_range_month(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")

    response = s.client.get(
        "/api/history/month", cookies=s.cookies, params={"year": 2026, "month": 13}
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_day_detail_rejects_a_malformed_date(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")

    response = s.client.get("/api/history/day", cookies=s.cookies, params={"date": "not-a-date"})

    assert response.status_code == 422


@pytest.mark.unit
def test_month_heatmap_counts_per_local_day_and_scopes_to_the_month(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "write report")

    _complete_pomodoro(s, task_id)  # 2026-01-01T00:25:00Z
    _complete_pomodoro(s, task_id)  # 2026-01-01T00:50:00Z
    s.clock.advance(24 * 3600)
    _complete_pomodoro(s, task_id)  # 2026-01-02T something

    assert _month(s, 2026, 1) == [
        {"day": "2026-01-01", "completed_count": 2},
        {"day": "2026-01-02", "completed_count": 1},
    ]
    assert _month(s, 2026, 2) == []


@pytest.mark.unit
def test_month_heatmap_does_not_leak_other_users_pomodoros(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "write report")
    _complete_pomodoro(s, task_id)

    other_client, other_cookies = _as_other_user(s)
    other_task = other_client.post("/api/tasks", cookies=other_cookies, json={"text": "their task"})
    other_client.post(
        "/api/timer/start", cookies=other_cookies, json={"task_id": other_task.json()["id"]}
    )
    other_client.get("/api/timer", cookies=other_cookies)

    response = other_client.get(
        "/api/history/month", cookies=other_cookies, params={"year": 2026, "month": 1}
    )
    assert response.json() == []


@pytest.mark.unit
def test_day_detail_reports_completed_count_and_dedicated_seconds(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "write report")
    _complete_pomodoro(s, task_id)

    result = _day(s, "2026-01-01")

    assert result == [
        {
            "task_id": task_id,
            "text": "write report",
            "tags": [],
            "completed_count": 1,
            "dedicated_seconds": 1500,
        }
    ]


@pytest.mark.unit
def test_day_detail_sums_interrupted_logged_time_without_counting_it_as_completed(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "write report")
    _log_interrupted(s, task_id, 300)

    result = _day(s, "2026-01-01")

    assert result == [
        {
            "task_id": task_id,
            "text": "write report",
            "tags": [],
            "completed_count": 0,
            "dedicated_seconds": 300,
        }
    ]


@pytest.mark.unit
def test_day_detail_filters_by_text_and_tags(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    informe_id = _create_task(s, "Informe")
    reunion_id = _create_task(s, "Reunión")
    s.client.patch(f"/api/tasks/{informe_id}/tags", cookies=s.cookies, json={"tags": ["urgente"]})
    _complete_pomodoro(s, informe_id)
    _complete_pomodoro(s, reunion_id)

    by_text = _day(s, "2026-01-01", text="inform")
    assert [entry["task_id"] for entry in by_text] == [informe_id]

    by_tag = _day(s, "2026-01-01", tags=["urgente"])
    assert [entry["task_id"] for entry in by_tag] == [informe_id]


@pytest.mark.unit
def test_day_detail_includes_archived_tasks_worked_that_day(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "old task")
    _complete_pomodoro(s, task_id)
    archive = s.client.post(f"/api/tasks/{task_id}/archive", cookies=s.cookies, json={})
    assert archive.status_code == 200

    result = _day(s, "2026-01-01")

    assert [entry["task_id"] for entry in result] == [task_id]


@pytest.mark.unit
def test_day_detail_does_not_leak_other_users_tasks(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "write report")
    _complete_pomodoro(s, task_id)

    other_client, other_cookies = _as_other_user(s)
    response = other_client.get(
        "/api/history/day", cookies=other_cookies, params={"date": "2026-01-01"}
    )
    assert response.status_code == 200
    assert response.json() == []
