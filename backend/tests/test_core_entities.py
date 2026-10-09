"""Tests for core/ entities, ids and normalization (T3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pomodoro.core.entities import (
    BreakKind,
    Pomodoro,
    PomodoroId,
    PomodoroStatus,
    Tag,
    TagId,
    Task,
    TaskId,
    TaskStatus,
    Timer,
    TimerPhase,
    User,
    UserId,
)
from pomodoro.core.normalization import normalize

pytestmark = pytest.mark.unit

_AWARE_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_NAIVE_NOW = datetime(2026, 1, 1)  # noqa: DTZ001 - deliberately naive, for the invariant test


class TestIdTypeDistinctness:
    def test_id_newtypes_are_distinct_objects(self) -> None:
        assert UserId is not TaskId
        assert TaskId is not TagId
        assert TagId is not PomodoroId
        assert UserId is not PomodoroId

    def test_id_newtypes_wrap_int_at_runtime(self) -> None:
        assert UserId(1) == 1
        assert TaskId(1) == TaskId(1)


class TestNormalizationEdgeCases:
    @pytest.mark.parametrize("value", [" Trabajo ", "TRABAJO", "trabajo", "  trabajo  "])
    def test_variants_normalize_equal(self, value: str) -> None:
        assert normalize(value) == "trabajo"

    def test_task_text_key_uses_the_shared_helper(self) -> None:
        task = Task(
            id=TaskId(1),
            user_id=UserId(1),
            text=" Trabajo ",
            position=0,
            created_at=_AWARE_NOW,
        )
        assert task.text_key == normalize(task.text) == "trabajo"

    def test_tag_name_key_uses_the_shared_helper(self) -> None:
        tag = Tag(id=TagId(1), user_id=UserId(1), name="URGENTE")
        assert tag.name_key == normalize(tag.name) == "urgente"

    def test_user_email_key_uses_the_shared_helper(self) -> None:
        user = User(
            id=UserId(1),
            email=" Someone@Example.com ",
            created_at=_AWARE_NOW,
            time_zone="UTC",
        )
        assert user.email_key == normalize(user.email) == "someone@example.com"


class TestAwareDatetimeInvariants:
    def test_user_rejects_naive_created_at(self) -> None:
        with pytest.raises(ValueError, match="aware datetime"):
            User(id=UserId(1), email="a@b.com", created_at=_NAIVE_NOW, time_zone="UTC")

    def test_task_rejects_naive_created_at(self) -> None:
        with pytest.raises(ValueError, match="aware datetime"):
            Task(
                id=TaskId(1),
                user_id=UserId(1),
                text="x",
                position=0,
                created_at=_NAIVE_NOW,
            )

    def test_task_rejects_naive_archived_at(self) -> None:
        with pytest.raises(ValueError, match="aware datetime"):
            Task(
                id=TaskId(1),
                user_id=UserId(1),
                text="x",
                position=0,
                created_at=_AWARE_NOW,
                archived_at=_NAIVE_NOW,
            )

    def test_pomodoro_rejects_naive_started_or_ended_at(self) -> None:
        with pytest.raises(ValueError, match="aware datetime"):
            Pomodoro(
                id=PomodoroId(1),
                user_id=UserId(1),
                task_id=TaskId(1),
                started_at=_NAIVE_NOW,
                ended_at=_AWARE_NOW,
                duration_seconds=1500,
                status=PomodoroStatus.COMPLETED,
            )

    def test_timer_rejects_naive_optional_timestamps(self) -> None:
        with pytest.raises(ValueError, match="aware datetime"):
            Timer(
                user_id=UserId(1),
                phase=TimerPhase.POMODORO_RUNNING,
                task_id=TaskId(1),
                phase_started_at=_NAIVE_NOW,
            )

    def test_timer_accepts_aware_timestamps_and_none(self) -> None:
        timer = Timer(
            user_id=UserId(1),
            phase=TimerPhase.BREAK_RUNNING,
            break_kind=BreakKind.LONG,
            phase_started_at=_AWARE_NOW,
            running_since=_AWARE_NOW,
        )
        assert timer.phase_ended_at is None


class TestTaskStatusDerivation:
    def test_active_task_has_no_archived_at(self) -> None:
        task = Task(id=TaskId(1), user_id=UserId(1), text="x", position=0, created_at=_AWARE_NOW)
        assert task.status is TaskStatus.ACTIVE

    def test_archived_task_has_archived_at_set(self) -> None:
        task = Task(
            id=TaskId(1),
            user_id=UserId(1),
            text="x",
            position=0,
            created_at=_AWARE_NOW,
            archived_at=_AWARE_NOW,
        )
        assert task.status is TaskStatus.ARCHIVED
