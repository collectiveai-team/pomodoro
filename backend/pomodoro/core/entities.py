"""Framework-free domain entities and their id types.

Zero imports of fastapi/sqlmodel/pydantic: this module is the foundation every
other core module builds on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from datetime import datetime

UserId = NewType("UserId", int)
TaskId = NewType("TaskId", int)
TagId = NewType("TagId", int)
PomodoroId = NewType("PomodoroId", int)
AuthSessionId = NewType("AuthSessionId", int)


class TaskStatus(Enum):
    """Whether a Task is selectable for a new Pomodoro or retired."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class PomodoroStatus(Enum):
    """How a Pomodoro ended."""

    COMPLETED = "completed"
    INTERRUPTED_LOGGED = "interrupted_logged"


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True)
class User:
    """A registered person; every Task, Tag, Pomodoro and preference belongs to one."""

    id: UserId
    email: str
    email_key: str
    created_at: datetime
    time_zone: str
    alarm_enabled: bool
    notifications_enabled: bool

    def __post_init__(self) -> None:
        _require_aware(self.created_at, field_name="created_at")


@dataclass(frozen=True)
class Task:
    """A unit of work; `archived_at is None` means Active."""

    id: TaskId
    user_id: UserId
    text: str
    position: int
    tag_ids: tuple[TagId, ...]
    created_at: datetime
    archived_at: datetime | None

    def __post_init__(self) -> None:
        _require_aware(self.created_at, field_name="created_at")
        if self.archived_at is not None:
            _require_aware(self.archived_at, field_name="archived_at")

    @property
    def status(self) -> TaskStatus:
        """Derive Active/Archived from `archived_at`."""
        return TaskStatus.ARCHIVED if self.archived_at is not None else TaskStatus.ACTIVE


@dataclass(frozen=True)
class AuthSession:
    """An opaque login session; only its token's hash is ever stored."""

    id: AuthSessionId
    user_id: UserId
    token_hash: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.created_at, field_name="created_at")
        _require_aware(self.last_used_at, field_name="last_used_at")
        _require_aware(self.expires_at, field_name="expires_at")


@dataclass(frozen=True)
class Tag:
    """A per-User label shared by every Task it's attached to."""

    id: TagId
    user_id: UserId
    name: str
    name_key: str


@dataclass(frozen=True)
class Pomodoro:
    """A completed or interrupted-and-logged focus interval dedicated to one Task."""

    id: PomodoroId
    user_id: UserId
    task_id: TaskId
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    status: PomodoroStatus

    def __post_init__(self) -> None:
        _require_aware(self.started_at, field_name="started_at")
        _require_aware(self.ended_at, field_name="ended_at")
