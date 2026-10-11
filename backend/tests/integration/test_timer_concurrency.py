"""Integration test: concurrent settles record a completed Pomodoro exactly once (ADR-0003)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from pomodoro.api.v1.timer.use_cases import _settle_and_persist
from pomodoro.core.timer import Timer, TimerPhase
from pomodoro.core.users import UserId
from pomodoro.database.models.pomodoro import PomodoroTable
from pomodoro.database.models.timer import TimerTable
from pomodoro.database.models.user import UserTable
from pomodoro.database.repositories.timer import SqlTimerRepository
from sqlmodel import Session, select
from tests.database.task_table_cases import add_task, make_user

if TYPE_CHECKING:
    from sqlalchemy import Engine

pytestmark = pytest.mark.integration


class _SlowReadTimerRepository(SqlTimerRepository):
    """Widens the read-to-commit window so unlocked concurrent requests reliably overlap."""

    def get(self, user_id):
        timer = super().get(user_id)
        time.sleep(0.3)
        return timer


def test_concurrent_settles_of_a_finished_pomodoro_record_it_once(
    postgres_engine: Engine,
) -> None:
    started = datetime.now(UTC) - timedelta(minutes=30)
    with Session(postgres_engine) as setup:
        user_id = make_user(setup, email="concurrent-settle@example.com")
        task_id = add_task(setup, user_id, "concurrent", 0)
        setup.add(
            TimerTable(
                user_id=user_id,
                phase=TimerPhase.POMODORO_RUNNING.value,
                task_id=task_id,
                phase_started_at=started,
                accumulated_active_seconds=0,
                running_since=started,
            )
        )
        setup.commit()

    def settle_once(_: int) -> Timer:
        with Session(postgres_engine) as worker:
            return _settle_and_persist(
                user_id=UserId(user_id),
                now=datetime.now(UTC),
                timer_repository=_SlowReadTimerRepository(worker),
            )

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(settle_once, range(4)))
        with Session(postgres_engine) as check:
            rows = check.exec(select(PomodoroTable).where(PomodoroTable.user_id == user_id)).all()
        assert len(rows) == 1
    finally:
        with Session(postgres_engine) as cleanup:
            for row in cleanup.exec(
                select(PomodoroTable).where(PomodoroTable.user_id == user_id)
            ).all():
                cleanup.delete(row)
            cleanup.commit()
            cleanup.delete(cleanup.get(UserTable, user_id))
            cleanup.commit()
