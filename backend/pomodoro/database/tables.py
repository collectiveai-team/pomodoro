"""Internal SQLModel table definitions. Never imported outside `pomodoro.database`."""

from datetime import datetime

from sqlmodel import CheckConstraint, Field, Index, SQLModel, UniqueConstraint, text

from pomodoro.database.types import UTCDateTime


class User(SQLModel, table=True):
    """A registered person; every domain table hangs off this one."""

    __tablename__ = "user"  # pyrefly: ignore[bad-override]

    id: int | None = Field(default=None, primary_key=True)
    email: str
    email_key: str = Field(unique=True, index=True)
    password_hash: str
    time_zone: str
    alarm_enabled: bool = True
    notifications_enabled: bool = True
    created_at: datetime = Field(sa_type=UTCDateTime)


class AuthSession(SQLModel, table=True):
    """An opaque login session; only its token's hash is stored."""

    __tablename__ = "auth_session"  # pyrefly: ignore[bad-override]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(sa_type=UTCDateTime)
    last_used_at: datetime = Field(sa_type=UTCDateTime)
    expires_at: datetime = Field(sa_type=UTCDateTime)


class Task(SQLModel, table=True):
    """A unit of work; `archived_at IS NULL` means Active."""

    __tablename__ = "task"  # pyrefly: ignore[bad-override]
    __table_args__ = (
        Index(
            "ix_task_user_id_text_key_active",
            "user_id",
            "text_key",
            unique=True,
            sqlite_where=text("archived_at IS NULL"),
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    text: str
    text_key: str
    position: int
    created_at: datetime = Field(sa_type=UTCDateTime)
    archived_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class Tag(SQLModel, table=True):
    """A per-User label shared by every Task it's attached to."""

    __tablename__ = "tag"  # pyrefly: ignore[bad-override]
    __table_args__ = (UniqueConstraint("user_id", "name_key", name="uq_tag_user_id_name_key"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    name: str
    name_key: str


class TaskTag(SQLModel, table=True):
    """The Task<->Tag assignment link table."""

    __tablename__ = "task_tags"  # pyrefly: ignore[bad-override]
    __table_args__ = (Index("ix_task_tags_tag_id", "tag_id"),)

    task_id: int = Field(foreign_key="task.id", ondelete="CASCADE", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE", primary_key=True)


class Pomodoro(SQLModel, table=True):
    """A completed or interrupted-and-logged focus interval dedicated to one Task."""

    __tablename__ = "pomodoro"  # pyrefly: ignore[bad-override]
    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="ck_pomodoro_duration_positive"),
        CheckConstraint("status IN ('completed', 'interrupted_logged')", name="ck_pomodoro_status"),
        CheckConstraint("ended_at >= started_at", name="ck_pomodoro_ended_after_started"),
        Index("ix_pomodoro_task_id", "task_id"),
        Index("ix_pomodoro_user_id_ended_at", "user_id", "ended_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE")
    task_id: int = Field(foreign_key="task.id", ondelete="RESTRICT")
    started_at: datetime = Field(sa_type=UTCDateTime)
    ended_at: datetime = Field(sa_type=UTCDateTime)
    duration_seconds: int
    status: str


class Timer(SQLModel, table=True):
    """A User's single live Pomodoro/Break state."""

    __tablename__ = "timer"  # pyrefly: ignore[bad-override]

    user_id: int = Field(foreign_key="user.id", ondelete="CASCADE", primary_key=True)
    phase: str
    task_id: int | None = Field(default=None, foreign_key="task.id")
    break_kind: str | None = None
    phase_started_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    accumulated_active_seconds: int = 0
    running_since: datetime | None = Field(default=None, sa_type=UTCDateTime)
    phase_ended_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    version: int = 0
