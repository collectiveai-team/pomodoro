"""Tests for the SQLModel schema and the first Alembic migration (T2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from pomodoro.database.engine import build_engine
from pomodoro.database.tables import AuthSession, Pomodoro, Task, User
from pomodoro.entrypoints.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

_EXPECTED_TABLES = {
    "user",
    "auth_session",
    "task",
    "tag",
    "task_tags",
    "pomodoro",
    "timer",
    "alembic_version",
}


def _upgrade_to_head(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    """Run `alembic upgrade head` against `database_url` via `env.py`'s real settings lookup.

    A standalone helper (not a fixture) so the equivalent `integration`-marked test
    against a real PostgreSQL service container (T18) can call it unchanged with a
    `postgresql://...` URL instead of a SQLite one.
    """
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(_ALEMBIC_INI)), "head")
    finally:
        get_settings.cache_clear()


@pytest.fixture
def migrated_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    database_url = f"sqlite:///{tmp_path / 'pomodoro.db'}"
    _upgrade_to_head(monkeypatch, database_url)
    engine = build_engine(database_url)
    with Session(engine) as session:
        yield session


def test_alembic_upgrade_head_creates_all_tables_from_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'pomodoro.db'}"

    _upgrade_to_head(monkeypatch, database_url)

    engine = build_engine(database_url)
    assert set(inspect(engine).get_table_names()) == _EXPECTED_TABLES


def _make_user(session: Session, *, email: str = "user@example.com") -> int:
    user = User(
        email=email,
        email_key=email,
        password_hash="hash",
        time_zone="UTC",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    assert user.id is not None
    return user.id


def _make_task(session: Session, user_id: int, *, text_key: str = "write") -> int:
    task = Task(
        user_id=user_id, text="Write", text_key=text_key, position=0, created_at=datetime.now(UTC)
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    assert task.id is not None
    return task.id


def test_partial_unique_index_allows_duplicate_text_key_once_archived(
    migrated_session: Session,
) -> None:
    session = migrated_session
    user_id = _make_user(session)
    now = datetime.now(UTC)

    _make_task(session, user_id)

    # Archiving frees the text_key: a second Active Task may reuse it.
    archived = session.exec(select(Task).where(Task.text_key == "write")).one()
    archived.archived_at = now
    session.add(archived)
    session.commit()

    session.add(Task(user_id=user_id, text="Write", text_key="write", position=1, created_at=now))
    session.commit()


def test_partial_unique_index_rejects_duplicate_active_text_key(
    migrated_session: Session,
) -> None:
    session = migrated_session
    user_id = _make_user(session)
    now = datetime.now(UTC)

    _make_task(session, user_id)
    session.add(Task(user_id=user_id, text="Write", text_key="write", position=1, created_at=now))

    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_a_user_cascades_to_their_auth_sessions(
    migrated_session: Session,
) -> None:
    session = migrated_session
    user_id = _make_user(session)
    now = datetime.now(UTC)
    session.add(
        AuthSession(
            user_id=user_id,
            token_hash="token-hash",
            created_at=now,
            last_used_at=now,
            expires_at=now,
        )
    )
    session.commit()

    user = session.get(User, user_id)
    assert user is not None
    session.delete(user)
    session.commit()

    assert session.exec(select(AuthSession)).all() == []


def test_deleting_a_task_with_a_pomodoro_is_restricted(migrated_session: Session) -> None:
    session = migrated_session
    user_id = _make_user(session)
    now = datetime.now(UTC)
    task_id = _make_task(session, user_id)

    session.add(
        Pomodoro(
            user_id=user_id,
            task_id=task_id,
            started_at=now,
            ended_at=now,
            duration_seconds=1500,
            status="completed",
        )
    )
    session.commit()

    task = session.get(Task, task_id)
    assert task is not None
    session.delete(task)
    with pytest.raises(IntegrityError):
        session.commit()
