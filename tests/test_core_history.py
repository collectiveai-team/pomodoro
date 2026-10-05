"""Unit tests for the core History aggregation rule: monthly heatmap and day detail."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from pomodoro.core.entities import (
    Pomodoro,
    PomodoroId,
    PomodoroStatus,
    Task,
    TaskId,
    UserId,
)
from pomodoro.core.history import (
    DayCount,
    TaskDaySummary,
    day_detail,
    month_bounds_utc,
    monthly_heatmap,
)

USER = UserId(1)
OTHER_USER = UserId(2)
TASK_A = TaskId(1)
TASK_B = TaskId(2)
CREATED = datetime(2026, 1, 1, tzinfo=UTC)

BUENOS_AIRES = "America/Argentina/Buenos_Aires"  # UTC-3, no DST
TOKYO = "Asia/Tokyo"  # UTC+9, no DST


def make_pomodoro(
    *,
    id: int,
    user_id: UserId = USER,
    task_id: TaskId = TASK_A,
    started_at: datetime = CREATED,
    ended_at: datetime,
    duration_seconds: int = 1500,
    status: PomodoroStatus = PomodoroStatus.COMPLETED,
) -> Pomodoro:
    return Pomodoro(
        id=PomodoroId(id),
        user_id=user_id,
        task_id=task_id,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        status=status,
    )


def make_task(*, id: int, text: str, archived_at: datetime | None = None) -> Task:
    return Task(
        id=TaskId(id),
        user_id=USER,
        text=text,
        position=0,
        tag_ids=(),
        created_at=CREATED,
        archived_at=archived_at,
    )


# --- month_bounds_utc -----------------------------------------------------------


def test_month_bounds_utc_covers_the_local_calendar_month() -> None:
    start, end = month_bounds_utc(2026, 1, BUENOS_AIRES)
    assert start == datetime(2026, 1, 1, 3, tzinfo=UTC)
    assert end == datetime(2026, 2, 1, 3, tzinfo=UTC)


def test_month_bounds_utc_rolls_over_into_next_year() -> None:
    start, end = month_bounds_utc(2026, 12, BUENOS_AIRES)
    assert start == datetime(2026, 12, 1, 3, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, 3, tzinfo=UTC)


# --- monthly_heatmap -------------------------------------------------------------


def test_monthly_heatmap_counts_completed_pomodoros_per_local_day() -> None:
    pomodoros = [
        make_pomodoro(id=1, ended_at=datetime(2026, 1, 5, 14, tzinfo=UTC)),
        make_pomodoro(id=2, ended_at=datetime(2026, 1, 5, 18, tzinfo=UTC)),
        make_pomodoro(id=3, ended_at=datetime(2026, 1, 6, 14, tzinfo=UTC)),
    ]
    result = monthly_heatmap(pomodoros, 2026, 1, "UTC")
    assert result == [
        DayCount(day=date(2026, 1, 5), completed_count=2),
        DayCount(day=date(2026, 1, 6), completed_count=1),
    ]


def test_monthly_heatmap_ignores_interrupted_logged_pomodoros() -> None:
    pomodoros = [
        make_pomodoro(
            id=1,
            ended_at=datetime(2026, 1, 5, 14, tzinfo=UTC),
            status=PomodoroStatus.INTERRUPTED_LOGGED,
        ),
    ]
    assert monthly_heatmap(pomodoros, 2026, 1, "UTC") == []


def test_monthly_heatmap_ignores_pomodoros_outside_the_requested_month() -> None:
    pomodoros = [make_pomodoro(id=1, ended_at=datetime(2026, 2, 1, 0, tzinfo=UTC))]
    assert monthly_heatmap(pomodoros, 2026, 1, "UTC") == []


def test_pomodoro_crossing_local_midnight_counts_on_the_later_day() -> None:
    # 23:30 UTC on Jan 5th is 00:30 local in Tokyo (UTC+9) on Jan 6th.
    pomodoro = make_pomodoro(id=1, ended_at=datetime(2026, 1, 5, 23, 30, tzinfo=UTC))
    result = monthly_heatmap([pomodoro], 2026, 1, TOKYO)
    assert result == [DayCount(day=date(2026, 1, 6), completed_count=1)]


def test_two_users_in_different_time_zones_at_the_same_instant_land_on_different_local_days() -> (
    None
):
    # 01:30 UTC on Jan 6th is 22:30 local in Buenos Aires (UTC-3) on Jan 5th,
    # but 10:30 local in Tokyo (UTC+9) on Jan 6th.
    instant = datetime(2026, 1, 6, 1, 30, tzinfo=UTC)
    pomodoro_a = make_pomodoro(id=1, user_id=USER, ended_at=instant)
    pomodoro_b = make_pomodoro(id=2, user_id=OTHER_USER, ended_at=instant)

    result_a = monthly_heatmap([pomodoro_a], 2026, 1, BUENOS_AIRES)
    result_b = monthly_heatmap([pomodoro_b], 2026, 1, TOKYO)

    assert result_a == [DayCount(day=date(2026, 1, 5), completed_count=1)]
    assert result_b == [DayCount(day=date(2026, 1, 6), completed_count=1)]


# --- day_detail -------------------------------------------------------------------


def test_day_detail_reports_completed_count_and_dedicated_seconds_per_task() -> None:
    tasks = [make_task(id=1, text="Informe")]
    pomodoros = [
        make_pomodoro(
            id=1, task_id=TASK_A, started_at=CREATED, ended_at=datetime(2026, 1, 5, 14, tzinfo=UTC)
        ),
        make_pomodoro(
            id=2,
            task_id=TASK_A,
            started_at=CREATED,
            ended_at=datetime(2026, 1, 5, 18, tzinfo=UTC),
            duration_seconds=600,
            status=PomodoroStatus.INTERRUPTED_LOGGED,
        ),
    ]
    result = day_detail(pomodoros, tasks, date(2026, 1, 5), "UTC")
    assert result == [TaskDaySummary(task=tasks[0], completed_count=1, dedicated_seconds=2100)]


def test_day_detail_only_counts_completed_toward_completed_count() -> None:
    tasks = [make_task(id=1, text="Informe")]
    pomodoros = [
        make_pomodoro(
            id=1,
            task_id=TASK_A,
            started_at=CREATED,
            ended_at=datetime(2026, 1, 5, 14, tzinfo=UTC),
            duration_seconds=300,
            status=PomodoroStatus.INTERRUPTED_LOGGED,
        ),
    ]
    result = day_detail(pomodoros, tasks, date(2026, 1, 5), "UTC")
    assert result == [TaskDaySummary(task=tasks[0], completed_count=0, dedicated_seconds=300)]


def test_day_detail_excludes_pomodoros_from_other_days() -> None:
    tasks = [make_task(id=1, text="Informe")]
    pomodoros = [
        make_pomodoro(
            id=1, task_id=TASK_A, started_at=CREATED, ended_at=datetime(2026, 1, 6, 14, tzinfo=UTC)
        ),
    ]
    assert day_detail(pomodoros, tasks, date(2026, 1, 5), "UTC") == []


def test_day_detail_includes_pomodoro_crossing_local_midnight_on_the_later_day() -> None:
    tasks = [make_task(id=1, text="Informe")]
    # 23:30 UTC on Jan 5th is 00:30 local in Tokyo on Jan 6th.
    pomodoro = make_pomodoro(
        id=1, task_id=TASK_A, started_at=CREATED, ended_at=datetime(2026, 1, 5, 23, 30, tzinfo=UTC)
    )
    assert day_detail([pomodoro], tasks, date(2026, 1, 6), TOKYO) == [
        TaskDaySummary(task=tasks[0], completed_count=1, dedicated_seconds=1500)
    ]
    assert day_detail([pomodoro], tasks, date(2026, 1, 5), TOKYO) == []


def test_day_detail_includes_archived_tasks_worked_that_day() -> None:
    archived = make_task(id=1, text="Vieja", archived_at=datetime(2026, 1, 10, tzinfo=UTC))
    pomodoro = make_pomodoro(
        id=1, task_id=TaskId(1), started_at=CREATED, ended_at=datetime(2026, 1, 5, 14, tzinfo=UTC)
    )
    result = day_detail([pomodoro], [archived], date(2026, 1, 5), "UTC")
    assert result == [TaskDaySummary(task=archived, completed_count=1, dedicated_seconds=1500)]


def test_day_detail_filters_by_text_query() -> None:
    tasks = [make_task(id=1, text="Informe"), make_task(id=2, text="Reunión")]
    ended = datetime(2026, 1, 5, 14, tzinfo=UTC)
    pomodoros = [
        make_pomodoro(id=1, task_id=TaskId(1), started_at=CREATED, ended_at=ended),
        make_pomodoro(id=2, task_id=TaskId(2), started_at=CREATED, ended_at=ended),
    ]
    result = day_detail(pomodoros, tasks, date(2026, 1, 5), "UTC", name_query="inform")
    assert [summary.task.id for summary in result] == [TaskId(1)]


def test_day_detail_with_multiple_tasks_worked_preserves_first_worked_order() -> None:
    tasks = [make_task(id=1, text="Primera"), make_task(id=2, text="Segunda")]
    base = datetime(2026, 1, 5, 10, tzinfo=UTC)
    pomodoros = [
        make_pomodoro(id=1, task_id=TaskId(2), started_at=CREATED, ended_at=base),
        make_pomodoro(
            id=2, task_id=TaskId(1), started_at=CREATED, ended_at=base + timedelta(hours=1)
        ),
    ]
    result = day_detail(pomodoros, tasks, date(2026, 1, 5), "UTC")
    assert [summary.task.id for summary in result] == [TaskId(2), TaskId(1)]
