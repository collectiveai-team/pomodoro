"""Tests for the T15 `api/v1/settings` router: read & update alarm/notifications/time_zone.

Drives the real app (`entrypoints.app.create_app`) through `TestClient` over an
in-memory SQLite database (the `_schema`/`client` conftest fixtures), never a
mocked repository - matching T10-T14's existing `api/v1` test style.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from sqlmodel import Session

from pomodoro.database import tables
from pomodoro.entrypoints.dependencies import get_engine

if TYPE_CHECKING:
    from datetime import tzinfo

    from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("_schema")]


def _get_settings(client: TestClient):
    return client.get("/api/v1/settings")


def _update_settings(client: TestClient, **fields: object):
    return client.patch("/api/v1/settings", json=fields)


def _user_id(client: TestClient) -> int:
    return client.get("/api/v1/auth/me").json()["id"]


def _seed_completed_pomodoro(*, user_id: int, ended_at: datetime) -> None:
    with Session(get_engine()) as session:
        task = tables.Task(
            user_id=user_id, text="Write", text_key="write", position=0, created_at=ended_at
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        assert task.id is not None
        session.add(
            tables.Pomodoro(
                user_id=user_id,
                task_id=task.id,
                started_at=ended_at - timedelta(minutes=25),
                ended_at=ended_at,
                duration_seconds=1500,
                status="completed",
            )
        )
        session.commit()


class TestGetSettings:
    def test_returns_the_registered_time_zone_and_default_preferences(
        self, client: TestClient
    ) -> None:
        response = _get_settings(client)

        assert response.status_code == 200
        body = response.json()
        assert body["time_zone"] == "America/Bogota"
        assert body["alarm_enabled"] is True
        assert body["notifications_enabled"] is True

    def test_get_without_a_session_is_rejected(self, anonymous_client: TestClient) -> None:
        assert _get_settings(anonymous_client).status_code == 401


class TestUpdateSettings:
    def test_updates_time_zone_independently(self, client: TestClient) -> None:
        response = _update_settings(client, time_zone="Europe/Madrid")

        assert response.status_code == 200
        body = response.json()
        assert body["time_zone"] == "Europe/Madrid"
        assert body["alarm_enabled"] is True
        assert body["notifications_enabled"] is True

    def test_updates_alarm_enabled_independently(self, client: TestClient) -> None:
        response = _update_settings(client, alarm_enabled=False)

        assert response.status_code == 200
        body = response.json()
        assert body["alarm_enabled"] is False
        assert body["time_zone"] == "America/Bogota"
        assert body["notifications_enabled"] is True

    def test_updates_notifications_enabled_independently(self, client: TestClient) -> None:
        response = _update_settings(client, notifications_enabled=False)

        assert response.status_code == 200
        body = response.json()
        assert body["notifications_enabled"] is False
        assert body["time_zone"] == "America/Bogota"
        assert body["alarm_enabled"] is True

    def test_a_subsequent_read_reflects_the_update(self, client: TestClient) -> None:
        _update_settings(client, alarm_enabled=False, time_zone="Europe/Madrid")

        response = _get_settings(client)

        assert response.json()["time_zone"] == "Europe/Madrid"
        assert response.json()["alarm_enabled"] is False

    def test_rejects_an_invalid_time_zone(self, client: TestClient) -> None:
        response = _update_settings(client, time_zone="Mars/Olympus_Mons")

        assert response.status_code == 400
        body = _get_settings(client)
        assert body.json()["time_zone"] == "America/Bogota"

    def test_update_without_a_session_is_rejected(self, anonymous_client: TestClient) -> None:
        response = _update_settings(anonymous_client, time_zone="Europe/Madrid")

        assert response.status_code == 401

    def test_update_without_json_content_type_is_rejected(self, client: TestClient) -> None:
        response = client.patch(
            "/api/v1/settings",
            data="time_zone=Europe/Madrid",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 403


class TestTimeZoneChangeAffectsHistoryRelevantAggregate:
    def test_changing_time_zone_immediately_changes_the_day_summary_grouping(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Fix "now" for the day-summary endpoint so the day-boundary crossing below is
        # deterministic regardless of the real wall-clock time the suite happens to run
        # at (mirrors `test_core_timer.py`'s `FakeClock`, applied at the API boundary
        # since `api.v1.routers.timer` calls `datetime.now(UTC)` directly, not via a
        # `Clock` port).
        fixed_now = datetime(2026, 1, 15, 2, 0, tzinfo=UTC)

        def _fixed_now(tz: tzinfo | None = None) -> datetime:
            return fixed_now if tz is None else fixed_now.astimezone(tz)

        fake_datetime = SimpleNamespace(now=_fixed_now)
        monkeypatch.setattr("pomodoro.api.v1.routers.timer.datetime", fake_datetime)

        # 2026-01-14T23:00:00Z is 2026-01-14 in UTC (yesterday relative to `fixed_now`'s
        # UTC date) but 2026-01-14 18:00 in America/Bogota (UTC-5) - the same calendar
        # day as `fixed_now` converted to Bogota (2026-01-14 21:00) - so this Pomodoro
        # counts as "completed today" only while the User's time_zone is still Bogota
        # (the conftest `client` fixture's registered default).
        ended_at = datetime(2026, 1, 14, 23, 0, tzinfo=UTC)
        user_id = _user_id(client)
        _seed_completed_pomodoro(user_id=user_id, ended_at=ended_at)

        before = client.get("/api/v1/timer/day-summary")
        assert before.status_code == 200
        assert before.json()["completed_today"] == 1

        _update_settings(client, time_zone="UTC")

        after = client.get("/api/v1/timer/day-summary")
        assert after.status_code == 200
        assert after.json()["completed_today"] == 0
