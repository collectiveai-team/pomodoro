"""Framework-free domain entities (ADR-0001, CES-16).

`User`, `Task`, `Tag`, `Pomodoro` and `Timer` as plain `@dataclass`es with
`NewType` ids and aware-`datetime` fields only — no `fastapi`, `sqlmodel` or
`pydantic` import belongs here (CES-79: `core` never hands a raw dict across a
boundary either). Lifecycle rules, validation and the Timer state machine are
separate tickets (T4/T5/T6/T7); this module only shapes the data they operate on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, NewType

from pomodoro.core.normalization import tag_name_key, task_text_key, user_email_key

if TYPE_CHECKING:
    from datetime import datetime

UserId = NewType("UserId", int)
TaskId = NewType("TaskId", int)
TagId = NewType("TagId", int)
PomodoroId = NewType("PomodoroId", int)
AuthSessionId = NewType("AuthSessionId", int)


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be an aware datetime, got a naive one")


class TaskStatus(StrEnum):
    """A Task's status, always derived from `archived_at` — never stored."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class PomodoroStatus(StrEnum):
    """How a finished Pomodoro run ended."""

    COMPLETED = "completed"
    INTERRUPTED_LOGGED = "interrupted_logged"


class TimerPhase(StrEnum):
    """The Timer state machine's phases (T6 implements the transitions)."""

    IDLE = "idle"
    POMODORO_RUNNING = "pomodoro_running"
    POMODORO_PAUSED = "pomodoro_paused"
    ASKING_TO_LOG = "asking_to_log"
    BREAK_RUNNING = "break_running"
    BREAK_PAUSED = "break_paused"
    READY_FOR_NEXT = "ready_for_next"


class BreakKind(StrEnum):
    """Break duration: short (5 min) or long (10 min), per the 5th-Pomodoro cadence."""

    SHORT = "short"
    LONG = "long"


@dataclass(frozen=True, slots=True)
class User:
    """A registered User and their preferences."""

    id: UserId
    email: str
    created_at: datetime
    time_zone: str
    alarm_enabled: bool = True
    notifications_enabled: bool = True

    def __post_init__(self) -> None:
        _require_aware(self.created_at, "created_at")

    @property
    def email_key(self) -> str:
        """The normalized comparison key for `email` (issue #12 spec)."""
        return user_email_key(self.email)


@dataclass(frozen=True, slots=True)
class Task:
    """A User's Task. `archived_at IS NULL` means Active; no own counters."""

    id: TaskId
    user_id: UserId
    text: str
    position: int
    created_at: datetime
    archived_at: datetime | None = None
    tag_ids: frozenset[TagId] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _require_aware(self.created_at, "created_at")
        if self.archived_at is not None:
            _require_aware(self.archived_at, "archived_at")

    @property
    def text_key(self) -> str:
        """The normalized comparison key for `text` (issue #12 spec)."""
        return task_text_key(self.text)

    @property
    def status(self) -> TaskStatus:
        """Active/Archived, derived from `archived_at`."""
        return TaskStatus.ARCHIVED if self.archived_at is not None else TaskStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class AuthSession:
    """A revocable, opaque-token login session for a User (T7/T8).

    The raw token is never stored or carried here, only `token_hash` — a hash of
    it, analogous to `User.password_hash` never appearing on `User` itself.
    """

    id: AuthSessionId
    user_id: UserId
    token_hash: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.created_at, "created_at")
        _require_aware(self.last_used_at, "last_used_at")
        _require_aware(self.expires_at, "expires_at")


@dataclass(frozen=True, slots=True)
class Tag:
    """A User's Tag; uniqueness is per-User, by normalized `name_key`."""

    id: TagId
    user_id: UserId
    name: str

    @property
    def name_key(self) -> str:
        """The normalized comparison key for `name` (issue #12 spec)."""
        return tag_name_key(self.name)


@dataclass(frozen=True, slots=True)
class Pomodoro:
    """A finished (completed or interrupted-and-logged) Pomodoro run."""

    id: PomodoroId
    user_id: UserId
    task_id: TaskId
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    status: PomodoroStatus

    def __post_init__(self) -> None:
        _require_aware(self.started_at, "started_at")
        _require_aware(self.ended_at, "ended_at")


@dataclass(frozen=True, slots=True)
class Timer:
    """Each User's single persisted Timer row (ADR-0003: resolved lazily, no ticks)."""

    user_id: UserId
    phase: TimerPhase
    task_id: TaskId | None = None
    break_kind: BreakKind | None = None
    phase_started_at: datetime | None = None
    accumulated_active_seconds: int = 0
    running_since: datetime | None = None
    phase_ended_at: datetime | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("phase_started_at", self.phase_started_at),
            ("running_since", self.running_since),
            ("phase_ended_at", self.phase_ended_at),
        ):
            if value is not None:
                _require_aware(value, name)
