"""Simulated-concurrency tests for T13's CAS guard on `SqlTimerRepository.apply`.

Two regression guards from a prior (pre-CES) build: two simultaneous requests
that both observe a Pomodoro past its deadline must not persist two
completed-Pomodoro rows for the same run, and submitting `log` twice for the
same interrupted Pomodoro must record it once. Both scenarios use a
`threading.Barrier` to force two threads to read the same Timer row *before*
either is allowed to write, so the race is genuinely exercised rather than
just sequentially simulated.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func
from sqlmodel import Session, select

from pomodoro.core import timer as core_timer
from pomodoro.core.entities import PomodoroStatus, TaskId, Timer, TimerPhase, UserId
from pomodoro.core.errors import TimerActionNotAllowedError
from pomodoro.core.timer import TimerUpdate
from pomodoro.database import tables
from pomodoro.database.engine import build_engine
from pomodoro.database.tables import SQLModel
from pomodoro.database.timer_repository import SqlTimerRepository

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit

_USER = UserId(1)
_TASK = TaskId(1)
_EPOCH = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    # A file-backed database, not `sqlite://`'s shared in-memory `StaticPool` connection:
    # two threads genuinely racing requires each to hold its own DBAPI connection, which
    # SQLite's own file-level locking then serializes safely - a single shared connection
    # object is not safe to use concurrently from two threads even with
    # `check_same_thread=False` (python's `sqlite3` module raises "bad parameter or other
    # API misuse" under real concurrent access to one connection).
    engine = build_engine(f"sqlite:///{tmp_path / 'pomodoro.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            tables.User(
                id=1,
                email="a@example.com",
                email_key="a@example.com",
                password_hash="hash",
                time_zone="UTC",
                created_at=_EPOCH,
            )
        )
        session.commit()
        session.add(
            tables.Task(
                id=1, user_id=1, text="Write", text_key="write", position=0, created_at=_EPOCH
            )
        )
        session.commit()
    return engine


def _pomodoro_count(engine: Engine) -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(tables.Pomodoro)).one()


def _start(engine: Engine, *, now: datetime = _EPOCH) -> None:
    with Session(engine) as session:
        SqlTimerRepository(session).apply(
            _USER, lambda t: TimerUpdate(timer=core_timer.start(t, task_id=_TASK, now=now))
        )


def _run_concurrently(
    engine: Engine, mutate_factory: Callable[[Timer], TimerUpdate]
) -> tuple[list[TimerUpdate], list[BaseException]]:
    """Run `mutate_factory` through `SqlTimerRepository.apply` on two threads at once.

    Each thread waits at a shared barrier right after its *first* read of the
    Timer row (inside `mutate_factory`), so both threads are guaranteed to have
    observed the same pre-write state before either is allowed to proceed -
    genuine interleaving, not a sequential approximation of it. A retry inside
    `apply` (after losing the CAS race) skips the barrier, since by then the
    other thread has already finished.
    """
    barrier = threading.Barrier(2)
    results: list[TimerUpdate] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        used_barrier = False

        def mutate(current: Timer) -> TimerUpdate:
            nonlocal used_barrier
            result = mutate_factory(current)
            if not used_barrier:
                used_barrier = True
                barrier.wait(timeout=5)
            return result

        try:
            with Session(engine) as session:
                outcome = SqlTimerRepository(session).apply(_USER, mutate)
            with lock:
                results.append(outcome)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    return results, errors


class TestSettleAndPersistConcurrency:
    def test_two_simultaneous_settles_never_duplicate_the_completed_pomodoro(
        self, engine: Engine
    ) -> None:
        _start(engine)
        now = _EPOCH + timedelta(seconds=core_timer.POMODORO_SECONDS + 3600)

        results, errors = _run_concurrently(engine, lambda t: core_timer.settle(t, now))

        assert errors == []
        assert len(results) == 2
        assert sum(1 for result in results if result.pomodoro is not None) == 1
        assert _pomodoro_count(engine) == 1
        with Session(engine) as session:
            row = session.get(tables.Timer, 1)
            assert row is not None
            assert row.phase == TimerPhase.READY_FOR_NEXT.value
            assert row.version == 2  # one write for `start`, exactly one more for `settle`


class TestLogDoubleSubmitConcurrency:
    def test_two_simultaneous_logs_record_the_interrupted_pomodoro_once(
        self, engine: Engine
    ) -> None:
        _start(engine)
        stop_instant = _EPOCH + timedelta(seconds=600)
        with Session(engine) as session:
            SqlTimerRepository(session).apply(
                _USER,
                lambda t: TimerUpdate(timer=core_timer.stop(t, now=stop_instant)),
            )

        results, errors = _run_concurrently(engine, core_timer.log)

        assert len(results) == 1
        assert len(errors) == 1
        assert isinstance(errors[0], TimerActionNotAllowedError)
        assert results[0].pomodoro is not None
        assert results[0].pomodoro.status is PomodoroStatus.INTERRUPTED_LOGGED
        assert _pomodoro_count(engine) == 1
        with Session(engine) as session:
            row = session.get(tables.Timer, 1)
            assert row is not None
            assert row.phase == TimerPhase.IDLE.value
