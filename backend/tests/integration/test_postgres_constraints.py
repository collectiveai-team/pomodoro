"""Integration tests: the critical cross-cutting rules hold on real PostgreSQL (T19, ADR-0002).

Mirrors proofs already covered against SQLite (`tests/database/test_task_table.py`, the
account-deletion coverage under `tests/api/test_auth_account_management.py`) against real
PostgreSQL, since SQLite and PostgreSQL diverge on partial-index support, FK-enforcement
defaults, and `timestamptz` round-tripping. `session` (see `conftest.py`) points at a database
whose schema came from Alembic's migration chain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from pomodoro.core.history import aggregate_pomodoros_by_day
from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import Pomodoro, PomodoroStatus
from pomodoro.core.users import UserId
from pomodoro.database.models.auth_session import AuthSessionTable
from pomodoro.database.models.pomodoro import PomodoroTable
from pomodoro.database.models.tag import TagTable
from pomodoro.database.models.task import TaskTable
from pomodoro.database.models.timer import TimerTable
from pomodoro.database.models.user import UserTable
from pomodoro.database.repositories.pomodoro import SqlPomodoroRepository
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from tests.database.task_table_cases import (
    add_task,
    assert_an_archived_task_does_not_block_an_active_task_with_the_same_text_key,
    assert_two_active_tasks_with_the_same_text_key_are_rejected,
    make_user,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel import Session

pytestmark = pytest.mark.integration


def _add_tag(session: Session, user_id: UUID, *, name: str, name_key: str) -> None:
    session.add(TagTable(user_id=user_id, name=name, name_key=name_key))
    session.commit()


def _add_pomodoro(session: Session, user_id: UUID, task_id: UUID) -> None:
    ended_at = datetime.now(UTC)
    session.add(
        PomodoroTable(
            user_id=user_id,
            task_id=task_id,
            started_at=ended_at - timedelta(minutes=25),
            ended_at=ended_at,
            duration_seconds=25 * 60,
            status=PomodoroStatus.COMPLETED.value,
        )
    )
    session.commit()


# --- Active-Task unique partial index (`ix_task_user_id_text_key_active`) ---


def test_two_active_tasks_with_the_same_text_key_are_rejected(session: Session) -> None:
    assert_two_active_tasks_with_the_same_text_key_are_rejected(session)


def test_an_archived_task_does_not_block_an_active_task_with_the_same_text_key(
    session: Session,
) -> None:
    assert_an_archived_task_does_not_block_an_active_task_with_the_same_text_key(session)


# --- Tag unique-per-User (`ix_tag_user_id_name_key`) ---


def test_two_tags_with_the_same_name_key_for_one_user_are_rejected(session: Session) -> None:
    user_id = make_user(session)
    _add_tag(session, user_id, name="Trabajo", name_key="trabajo")

    with pytest.raises(IntegrityError):
        _add_tag(session, user_id, name="trabajo", name_key="trabajo")
    session.rollback()


def test_two_different_users_may_share_the_same_tag_name_key(session: Session) -> None:
    first_user_id = make_user(session, email="first@example.com")
    second_user_id = make_user(session, email="second@example.com")
    _add_tag(session, first_user_id, name="Trabajo", name_key="trabajo")

    _add_tag(session, second_user_id, name="Trabajo", name_key="trabajo")  # must not raise


# --- History time-zone aggregation, round-tripped through `timestamptz` ---


def test_history_aggregation_round_trips_through_postgresql_timestamptz(session: Session) -> None:
    user_id = make_user(session)
    task_id = add_task(session, user_id, "deep work", 0)
    # 23:30 UTC on 2026-03-01 is 00:30 on 2026-03-02 in Europe/Paris.
    ended_at = datetime(2026, 3, 1, 23, 30, tzinfo=UTC)
    pomodoro = Pomodoro(
        task_id=TaskId(task_id),
        started_at=ended_at - timedelta(minutes=25),
        ended_at=ended_at,
        duration_seconds=25 * 60,
        status=PomodoroStatus.COMPLETED,
    )
    repository = SqlPomodoroRepository(session)
    repository.add(UserId(user_id), pomodoro)

    stored = repository.list_for_user(UserId(user_id))

    assert stored[0].ended_at == ended_at
    days = aggregate_pomodoros_by_day(stored, time_zone="Europe/Paris")
    assert days[0].day == datetime(2026, 3, 2, tzinfo=UTC).date()
    assert days[0].completed_count == 1


# --- Account cascade delete respects the Pomodoro `task_id` RESTRICT ---


def test_deleting_a_task_with_a_pomodoro_is_restricted(session: Session) -> None:
    user_id = make_user(session)
    task_id = add_task(session, user_id, "write report", 0)
    _add_pomodoro(session, user_id, task_id)

    session.delete(session.get(TaskTable, task_id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_deleting_the_user_cascades_every_owned_table_despite_the_pomodoro_restrict(
    session: Session,
) -> None:
    user_id = make_user(session)
    task_id = add_task(session, user_id, "write report", 0)
    _add_pomodoro(session, user_id, task_id)
    session.add(TagTable(user_id=user_id, name="urgent", name_key="urgent"))
    session.add(
        AuthSessionTable(
            user_id=user_id,
            token_hash="token-hash",
            created_at=datetime.now(UTC),
            last_used_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )
    session.add(TimerTable(user_id=user_id, phase="PomodoroRunning", task_id=task_id))
    session.commit()

    session.delete(session.get(UserTable, user_id))
    session.commit()  # must not raise despite pomodoro.task_id/timer.task_id ON DELETE RESTRICT

    for table in (UserTable, AuthSessionTable, TaskTable, TagTable, TimerTable, PomodoroTable):
        rows = session.exec(select(table)).all()
        assert rows == [], f"orphaned rows remain in {table.__tablename__}"
