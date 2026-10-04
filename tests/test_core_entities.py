"""Unit tests for the framework-free core entities, ids, normalization, and errors."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pomodoro.core.entities import (
    Pomodoro,
    PomodoroId,
    PomodoroStatus,
    Tag,
    TagId,
    Task,
    TaskId,
    TaskStatus,
    User,
    UserId,
)
from pomodoro.core.errors import (
    DomainError,
    DuplicateActiveTaskTextError,
    DuplicateTagNameError,
    EmailAlreadyRegisteredError,
    InvalidEmailError,
    InvalidPasswordLengthError,
    TagNameEmptyError,
    TaskHasPomodorosError,
    TaskInProgressError,
    TaskTextEmptyError,
    TaskTextTooLongError,
    UnarchiveCollisionError,
)
from pomodoro.core.normalization import normalize_key

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_user_construction() -> None:
    user = User(
        id=UserId(1),
        email="person@example.com",
        email_key="person@example.com",
        created_at=NOW,
        time_zone="America/Argentina/Buenos_Aires",
        alarm_enabled=True,
        notifications_enabled=False,
    )
    assert user.id == 1
    assert user.alarm_enabled is True
    assert user.notifications_enabled is False


def test_user_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        User(
            id=UserId(1),
            email="person@example.com",
            email_key="person@example.com",
            created_at=datetime(2026, 1, 1),  # noqa: DTZ001 - deliberately naive
            time_zone="UTC",
            alarm_enabled=True,
            notifications_enabled=True,
        )


def test_task_status_derives_from_archived_at() -> None:
    active = Task(
        id=TaskId(1),
        user_id=UserId(1),
        text="Write report",
        position=0,
        tag_ids=(),
        created_at=NOW,
        archived_at=None,
    )
    archived = Task(
        id=TaskId(2),
        user_id=UserId(1),
        text="Old task",
        position=0,
        tag_ids=(TagId(1),),
        created_at=NOW,
        archived_at=NOW,
    )
    assert active.status is TaskStatus.ACTIVE
    assert archived.status is TaskStatus.ARCHIVED
    assert archived.tag_ids == (TagId(1),)


def test_task_rejects_naive_archived_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Task(
            id=TaskId(1),
            user_id=UserId(1),
            text="Task",
            position=0,
            tag_ids=(),
            created_at=NOW,
            archived_at=datetime(2026, 1, 2),  # noqa: DTZ001 - deliberately naive
        )


def test_tag_construction() -> None:
    tag = Tag(id=TagId(1), user_id=UserId(1), name="Trabajo", name_key="trabajo")
    assert tag.name == "Trabajo"
    assert tag.name_key == "trabajo"


def test_pomodoro_construction() -> None:
    pomodoro = Pomodoro(
        id=PomodoroId(1),
        user_id=UserId(1),
        task_id=TaskId(1),
        started_at=NOW,
        ended_at=NOW,
        duration_seconds=1500,
        status=PomodoroStatus.COMPLETED,
    )
    assert pomodoro.status is PomodoroStatus.COMPLETED
    assert pomodoro.duration_seconds == 1500


def test_pomodoro_rejects_naive_started_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Pomodoro(
            id=PomodoroId(1),
            user_id=UserId(1),
            task_id=TaskId(1),
            started_at=datetime(2026, 1, 1),  # noqa: DTZ001 - deliberately naive
            ended_at=NOW,
            duration_seconds=1500,
            status=PomodoroStatus.COMPLETED,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" Trabajo ", "trabajo"),
        ("trabajo", "trabajo"),
        ("TRABAJO", "trabajo"),
        ("  Café con leche  ", "café con leche"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_key(value: str, expected: str) -> None:
    assert normalize_key(value) == expected


def test_normalize_key_treats_case_and_whitespace_variants_as_equal() -> None:
    assert normalize_key(" Trabajo ") == normalize_key("trabajo")


@pytest.mark.parametrize(
    "error",
    [
        TaskTextEmptyError(),
        TaskTextTooLongError(),
        DuplicateActiveTaskTextError(),
        UnarchiveCollisionError(),
        TagNameEmptyError(),
        DuplicateTagNameError(),
        TaskHasPomodorosError(),
        TaskInProgressError(),
        InvalidEmailError(),
        EmailAlreadyRegisteredError(),
        InvalidPasswordLengthError(),
    ],
)
def test_domain_errors_carry_a_clear_message(error: DomainError) -> None:
    assert isinstance(error, DomainError)
    message = str(error)
    assert message
    assert "Traceback" not in message


def test_task_text_too_long_error_mentions_the_limit() -> None:
    assert "200" in str(TaskTextTooLongError())


def test_invalid_password_length_error_mentions_the_bounds() -> None:
    message = str(InvalidPasswordLengthError())
    assert "8" in message
    assert "128" in message
