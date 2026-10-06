"""Regression tests for two Timer invariants the HTTP surface must hold.

1. A single Pomodoro must be persisted exactly once, no matter how many
   requests observe the same settle-able Timer at once.
   `settle_and_persist_with_version` (and the `/log` route) now read the
   Timer's storage version alongside its state and persist through a
   compare-and-swap write, so only the request that wins the race inserts the
   Pomodoro; the other re-reads the now-settled row and finds nothing left to
   do. The app itself issues concurrent `GET /api/timer` pairs on mount and on
   every focus regain. A single `TimerEngine` is shared between the mounted
   `TimerPanel` and `ActiveTab`; stories 64-68 also promise that the server
   Timer remains one shared Timer across browser tabs and devices.

   The interleaving is forced through a `TimerRepository` decorator that
   holds every reader at a barrier until both have read, rather than left to
   thread scheduling: the window is real but narrow, and a regression test
   that only fails most of the time is worse than none (`pytest-randomly`
   and the house test strategy both require deterministic tests).

2. A Pomodoro belongs to the local day it actually ended on (story 80). For
   a stopped-and-logged Pomodoro that is the instant the User stopped it
   (`Timer.phase_ended_at`, set by `stop()`), not
   `phase_started_at + accumulated_active_seconds`, which silently subtracts
   every paused gap from the recorded end instant.

Same `tmp_path`-backed SQLite setup as `test_timer_api.py`.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

import pytest
from pomodoro.api import tasks
from pomodoro.database import tables
from sqlmodel import Session, select

from tests.barriered_repository import BarrieredRepository
from tests.conftest import AuthedSession as _AuthedSession
from tests.conftest import authed_session as _authed_session
from tests.conftest import create_task as _create_task

if TYPE_CHECKING:
    from pathlib import Path


JSON_HEADERS = {"Content-Type": "application/json"}
CONCURRENT_REQUESTS = 2


def _action(s: _AuthedSession, path: str, body: dict[str, Any] | None = None) -> Any:
    return s.client.post(
        f"/api/timer/{path}", cookies=s.cookies, json=body or {}, headers=JSON_HEADERS
    )


def _persisted_pomodoros(s: _AuthedSession) -> list[tables.Pomodoro]:
    with Session(s.engine) as session:
        return list(session.exec(select(tables.Pomodoro)).all())


def _race(s: _AuthedSession, call: Any) -> list[Any]:
    """Run `call` from `CONCURRENT_REQUESTS` threads, all reading the Timer first."""
    overrides = s.client.app.dependency_overrides  # type: ignore[attr-defined]
    inner = overrides[tasks.get_timer_repository]()
    gated = BarrieredRepository(inner, CONCURRENT_REQUESTS, "get_with_version")
    overrides[tasks.get_timer_repository] = lambda: gated
    try:
        results: list[Any] = []
        lock = threading.Lock()

        def run() -> None:
            result = call()
            with lock:
                results.append(result)

        threads = [threading.Thread(target=run) for _ in range(CONCURRENT_REQUESTS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        return results
    finally:
        overrides[tasks.get_timer_repository] = lambda: inner


@pytest.mark.unit
def test_concurrent_reads_of_an_elapsed_pomodoro_persist_it_exactly_once(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "Escribir el spec")
    assert _action(s, "start", {"task_id": task_id}).status_code == 200
    s.clock.advance(25 * 60)

    statuses = _race(s, lambda: s.client.get("/api/timer", cookies=s.cookies).status_code)

    assert statuses == [200, 200]
    assert [p.status for p in _persisted_pomodoros(s)] == ["completed"]
    summary = s.client.get("/api/timer/summary", cookies=s.cookies).json()
    assert summary["completed_today"] == 1
    assert summary["until_long_break"] == 4


@pytest.mark.unit
def test_concurrent_logs_of_one_stopped_pomodoro_persist_it_exactly_once(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "Revisar el diff")
    assert _action(s, "start", {"task_id": task_id}).status_code == 200
    s.clock.advance(300)
    assert _action(s, "stop").status_code == 200

    statuses = _race(s, lambda: _action(s, "log").status_code)

    assert sorted(statuses) == [200, 409]
    assert [p.duration_seconds for p in _persisted_pomodoros(s)] == [300]
    detail = s.client.get(
        "/api/history/day", cookies=s.cookies, params={"date": "2026-01-01"}
    ).json()
    assert [row["dedicated_seconds"] for row in detail] == [300]


@pytest.mark.unit
def test_interrupted_pomodoro_paused_across_midnight_counts_on_the_day_it_ended(
    tmp_path: Path,
) -> None:
    # The FakeClock starts at 2026-01-01T00:00Z; this User's zone is UTC.
    s = _authed_session(tmp_path, time_zone="UTC")
    task_id = _create_task(s, "Cruzar la medianoche")

    s.clock.advance(23 * 3600 + 50 * 60)  # 2026-01-01 23:50Z
    assert _action(s, "start", {"task_id": task_id}).status_code == 200
    s.clock.advance(2 * 60)  # 2 min of active work -> 23:52
    assert _action(s, "pause").status_code == 200
    s.clock.advance(18 * 60)  # paused straight across midnight -> 2026-01-02 00:10Z
    assert _action(s, "resume").status_code == 200
    s.clock.advance(3 * 60)  # 3 more min of active work -> 2026-01-02 00:13Z
    assert _action(s, "stop").status_code == 200
    assert _action(s, "log").status_code == 200

    first_day = s.client.get(
        "/api/history/day", cookies=s.cookies, params={"date": "2026-01-01"}
    ).json()
    second_day = s.client.get(
        "/api/history/day", cookies=s.cookies, params={"date": "2026-01-02"}
    ).json()

    assert first_day == []
    assert [row["dedicated_seconds"] for row in second_day] == [300]
