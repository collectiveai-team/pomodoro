"""Exercises the constraints declared on the domain tables against a real engine.

Each test hits SQLite through the same engine/session factory the app uses, so a
regression in a table's columns/constraints (not just the Python type annotations)
is caught.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from pomodoro.database.engine import create_db_engine
from pomodoro.database.tables import (
    AuthSession,
    Pomodoro,
    SQLModel,
    Tag,
    Task,
    TaskTag,
    Timer,
    User,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine import Engine

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _engine(tmp_path: Path) -> Engine:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'pomodoro.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


def _add_user(session: Session, email: str = "person@example.com") -> User:
    user = User(
        email=email,
        email_key=email,
        password_hash="hash",
        time_zone="UTC",
        created_at=NOW,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _add_task(
    session: Session,
    user_id: int,
    *,
    text: str = "Work",
    position: int = 0,
    archived_at: datetime | None = None,
) -> Task:
    task = Task(
        user_id=user_id,
        text=text,
        text_key=text.strip().casefold(),
        position=position,
        created_at=NOW,
        archived_at=archived_at,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def _seed_user_and_task(session: Session) -> tuple[int, int, Task]:
    user = _add_user(session)
    assert user.id is not None
    task = _add_task(session, user.id)
    assert task.id is not None
    return user.id, task.id, task


def _add_pomodoro(
    session: Session,
    *,
    user_id: int,
    task_id: int,
    duration_seconds: int = 1500,
    status: str = "completed",
    started_at: datetime = NOW,
    ended_at: datetime = NOW,
) -> Pomodoro:
    pomodoro = Pomodoro(
        user_id=user_id,
        task_id=task_id,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        status=status,
    )
    session.add(pomodoro)
    session.commit()
    session.refresh(pomodoro)
    return pomodoro


@pytest.mark.unit
def test_task_partial_unique_index_blocks_duplicate_active_text_only(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user = _add_user(session)
        assert user.id is not None
        user_id = user.id
        _add_task(session, user_id, text="Report", position=0)

        with pytest.raises(IntegrityError):
            _add_task(session, user_id, text="Report", position=1)
        session.rollback()

        archived = _add_task(session, user_id, text="Archived dup", position=2, archived_at=NOW)
        # Same normalized text on another Archived Task does not conflict with the
        # partial index (it only applies WHERE archived_at IS NULL).
        another_archived = _add_task(
            session, user_id, text="Archived dup", position=3, archived_at=NOW
        )
        assert archived.id != another_archived.id


@pytest.mark.unit
def test_tag_unique_constraint_scoped_per_user(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user_a = _add_user(session, email="a@example.com")
        user_b = _add_user(session, email="b@example.com")
        assert user_a.id is not None
        assert user_b.id is not None
        user_a_id, user_b_id = user_a.id, user_b.id

        session.add(Tag(user_id=user_a_id, name="Urgent", name_key="urgent"))
        session.commit()

        session.add(Tag(user_id=user_a_id, name="Urgent", name_key="urgent"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # The same normalized name under a different User is not a conflict.
        session.add(Tag(user_id=user_b_id, name="Urgent", name_key="urgent"))
        session.commit()


@pytest.mark.unit
def test_task_tags_cascade_delete_from_both_sides(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user = _add_user(session)
        assert user.id is not None
        user_id = user.id
        task = _add_task(session, user_id, text="Task one", position=0)
        other_task = _add_task(session, user_id, text="Task two", position=1)
        assert task.id is not None
        assert other_task.id is not None
        task_id, other_task_id = task.id, other_task.id
        tag = Tag(user_id=user_id, name="Tag", name_key="tag")
        session.add(tag)
        session.commit()
        session.refresh(tag)
        assert tag.id is not None
        tag_id = tag.id

        session.add(TaskTag(task_id=task_id, tag_id=tag_id))
        session.add(TaskTag(task_id=other_task_id, tag_id=tag_id))
        session.commit()

        session.delete(task)
        session.commit()
        remaining = session.get(TaskTag, (task_id, tag_id))
        assert remaining is None
        assert session.get(TaskTag, (other_task_id, tag_id)) is not None

        session.delete(tag)
        session.commit()
        assert session.get(TaskTag, (other_task_id, tag_id)) is None


@pytest.mark.unit
def test_pomodoro_check_constraint_duration_must_be_positive(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user_id, task_id, _task = _seed_user_and_task(session)

        with pytest.raises(IntegrityError):
            _add_pomodoro(session, user_id=user_id, task_id=task_id, duration_seconds=0)
        session.rollback()


@pytest.mark.unit
def test_pomodoro_check_constraint_status_must_be_known_value(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user_id, task_id, _task = _seed_user_and_task(session)

        with pytest.raises(IntegrityError):
            _add_pomodoro(session, user_id=user_id, task_id=task_id, status="bogus")
        session.rollback()


@pytest.mark.unit
def test_pomodoro_check_constraint_ended_at_must_not_precede_started_at(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user_id, task_id, _task = _seed_user_and_task(session)
        earlier = datetime(2025, 12, 31, tzinfo=UTC)

        with pytest.raises(IntegrityError):
            _add_pomodoro(
                session, user_id=user_id, task_id=task_id, started_at=NOW, ended_at=earlier
            )
        session.rollback()


@pytest.mark.unit
def test_pomodoro_task_id_restrict_blocks_task_delete(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user_id, task_id, task = _seed_user_and_task(session)
        pomodoro = _add_pomodoro(session, user_id=user_id, task_id=task_id)

        session.delete(task)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        assert session.get(Task, task_id) is not None
        assert session.get(Pomodoro, pomodoro.id) is not None


@pytest.mark.unit
def test_user_delete_cascades_to_all_owned_rows(tmp_path: Path) -> None:
    engine = _engine(tmp_path)

    with Session(engine) as session:
        user = _add_user(session)
        assert user.id is not None
        owner_id = user.id
        task = _add_task(session, owner_id)
        assert task.id is not None
        owned_task_id = task.id
        tag = Tag(user_id=owner_id, name="Tag", name_key="tag")
        session.add(tag)
        session.commit()
        session.refresh(tag)
        assert tag.id is not None
        owned_tag_id = tag.id
        session.add(TaskTag(task_id=owned_task_id, tag_id=owned_tag_id))
        session.commit()

        pomodoro = _add_pomodoro(session, user_id=owner_id, task_id=owned_task_id)
        session.add(Timer(user_id=owner_id, phase="Idle"))
        session.add(
            AuthSession(
                user_id=owner_id,
                token_hash="tok",
                created_at=NOW,
                last_used_at=NOW,
                expires_at=NOW,
            )
        )
        session.commit()

        user_id, task_id, tag_id, pomodoro_id = owner_id, owned_task_id, owned_tag_id, pomodoro.id

        session.delete(session.get(User, user_id))
        session.commit()

        assert session.get(User, user_id) is None
        assert session.get(Task, task_id) is None
        assert session.get(Tag, tag_id) is None
        assert session.get(TaskTag, (task_id, tag_id)) is None
        assert session.get(Pomodoro, pomodoro_id) is None
        assert session.get(Timer, user_id) is None
        assert (
            session.exec(select(AuthSession).where(AuthSession.user_id == user_id)).first() is None
        )
