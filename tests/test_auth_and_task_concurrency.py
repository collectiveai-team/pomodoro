"""Regression tests for three contract gaps on the auth/task HTTP surface.

1. `POST /api/auth/register` used to store any `time_zone` string verbatim.
   `core.auth.validate_time_zone` already existed and was wired into `PATCH
   /api/settings`, but not into registration, so an unresolvable zone was
   accepted and every later `/api/timer/summary` and `/api/history/*` read
   for that account raised an uncaught `ZoneInfoNotFoundError` (story 5).

2. Concurrent creates of the same Task text, or registrations of the same
   email, used to surface database uniqueness as an unhandled `IntegrityError`
   instead of the 409 their single-threaded paths already produce (stories 2
   and 19): the pre-check (`list_active`/`get_by_email_key`) and the insert
   are two separate, un-transactioned calls, so two racers can both pass the
   pre-check before either writes.

Same `tmp_path`-backed SQLite setup as `test_tasks_api.py`/`test_auth_api.py`.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest
from pomodoro.api import auth, tasks

from tests.barriered_repository import BarrieredRepository
from tests.conftest import authed_session as _authed_session

if TYPE_CHECKING:
    from pathlib import Path

JSON_HEADERS = {"Content-Type": "application/json"}
UNRESOLVABLE_ZONE = "Not/AZone"


@pytest.mark.unit
def test_register_rejects_a_time_zone_the_server_cannot_resolve(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")

    response = s.client.post(
        "/api/auth/register",
        json={
            "email": "zona@example.com",
            "password": "correct horse",
            "time_zone": UNRESOLVABLE_ZONE,
        },
        headers=JSON_HEADERS,
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_concurrent_creates_of_the_same_task_text_report_the_duplicate_as_a_conflict(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    overrides = s.client.app.dependency_overrides  # type: ignore[attr-defined]
    inner = overrides[tasks.get_task_repository]()
    gated = BarrieredRepository(inner, 2, "list_active")
    overrides[tasks.get_task_repository] = lambda: gated

    outcomes: list[str] = []
    lock = threading.Lock()

    def create() -> None:
        try:
            status = str(
                s.client.post(
                    "/api/tasks",
                    cookies=s.cookies,
                    json={"text": "duplicada"},
                    headers=JSON_HEADERS,
                ).status_code
            )
        except Exception as error:
            status = type(error).__name__
        with lock:
            outcomes.append(status)

    try:
        threads = [threading.Thread(target=create) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        overrides[tasks.get_task_repository] = lambda: inner

    assert sorted(outcomes) == ["201", "409"]
    listed = s.client.get("/api/tasks/active", cookies=s.cookies).json()
    assert [task["text"] for task in listed] == ["duplicada"]


@pytest.mark.unit
def test_concurrent_registrations_of_the_same_email_report_the_duplicate_as_a_conflict(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    overrides = s.client.app.dependency_overrides  # type: ignore[attr-defined]
    inner = overrides[auth.get_user_repository]()
    gated = BarrieredRepository(inner, 2, "get_by_email_key")
    overrides[auth.get_user_repository] = lambda: gated

    outcomes: list[str] = []
    lock = threading.Lock()

    def register() -> None:
        try:
            status = str(
                s.client.post(
                    "/api/auth/register",
                    json={
                        "email": "duplicate@example.com",
                        "password": "correct horse",
                        "time_zone": "UTC",
                    },
                    headers=JSON_HEADERS,
                ).status_code
            )
        except Exception as error:
            status = type(error).__name__
        with lock:
            outcomes.append(status)

    try:
        threads = [threading.Thread(target=register) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        overrides[auth.get_user_repository] = lambda: inner

    assert sorted(outcomes) == ["201", "409"]
