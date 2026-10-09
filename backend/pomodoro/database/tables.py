"""SQLModel table classes (CES-18): the only place `table=True` models live.

Never imported by `core` or `api` — those layers see repository-returned dataclasses
(CES-79), never these ORM rows, per ADR-0002.

Every `__tablename__` assignment below carries a `# pyrefly: ignore[bad-override]`:
SQLModel declares `__tablename__` as a SQLAlchemy `declared_attr` descriptor, and
pyrefly's override check flags any subclass that overrides it with a plain string as
inconsistent (`must both be descriptors`) even though this is SQLModel's documented,
intended usage — a known false positive for every `table=True` model, not a defect here.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """A registered User and their preferences."""

    __tablename__ = "user"  # pyrefly: ignore[bad-override]

    id: int | None = Field(default=None, primary_key=True)
    email: str
    email_key: str = Field(sa_column=sa.Column(sa.String, unique=True, nullable=False))
    password_hash: str
    time_zone: str
    alarm_enabled: bool = Field(default=True)
    notifications_enabled: bool = Field(default=True)
    created_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))


class AuthSession(SQLModel, table=True):
    """A revocable, opaque-token login session for a User."""

    __tablename__ = "auth_session"  # pyrefly: ignore[bad-override]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    token_hash: str = Field(sa_column=sa.Column(sa.String, unique=True, nullable=False))
    created_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    last_used_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))

    __table_args__ = (sa.Index("ix_auth_session_user_id", "user_id"),)


class Task(SQLModel, table=True):
    """A User's Task; `archived_at IS NULL` means Active."""

    __tablename__ = "task"  # pyrefly: ignore[bad-override]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    text: str
    text_key: str
    position: int
    created_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    archived_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True)
    )

    __table_args__ = (
        sa.Index("ix_task_user_id", "user_id"),
        # Partial unique index: Active Task text must be unique per User, but an
        # Archived Task never blocks reuse of its text. `sqlite_where`/`postgresql_where`
        # render the same WHERE clause on both engines (ADR-0002).
        sa.Index(
            "ix_task_active_text_key",
            "user_id",
            "text_key",
            unique=True,
            sqlite_where=sa.text("archived_at IS NULL"),
            postgresql_where=sa.text("archived_at IS NULL"),
        ),
    )


class Tag(SQLModel, table=True):
    """A User's Tag; name uniqueness is per-User, by normalized `name_key`."""

    __tablename__ = "tag"  # pyrefly: ignore[bad-override]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    name: str
    name_key: str

    __table_args__ = (
        sa.Index("ix_tag_user_id", "user_id"),
        sa.UniqueConstraint("user_id", "name_key", name="uq_tag_user_id_name_key"),
    )


class TaskTags(SQLModel, table=True):
    """Task<->Tag assignment; cascades off either side, never orphaning a row."""

    __tablename__ = "task_tags"  # pyrefly: ignore[bad-override]

    task_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("task.id", ondelete="CASCADE"), primary_key=True)
    )
    tag_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
    )

    __table_args__ = (sa.Index("ix_task_tags_tag_id", "tag_id"),)


class Pomodoro(SQLModel, table=True):
    """A finished (completed or interrupted-and-logged) Pomodoro run."""

    __tablename__ = "pomodoro"  # pyrefly: ignore[bad-override]

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    # RESTRICT, not CASCADE: a Task with any Pomodoro can never be hard-deleted
    # (only archived), so History never loses rows out from under it.
    task_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("task.id", ondelete="RESTRICT"), nullable=False)
    )
    started_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    ended_at: datetime = Field(sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False))
    duration_seconds: int
    status: str

    __table_args__ = (
        sa.CheckConstraint("duration_seconds > 0", name="ck_pomodoro_duration_positive"),
        sa.CheckConstraint(
            "status IN ('completed', 'interrupted_logged')", name="ck_pomodoro_status_valid"
        ),
        sa.CheckConstraint("ended_at >= started_at", name="ck_pomodoro_ended_after_started"),
        sa.Index("ix_pomodoro_task_id", "task_id"),
        sa.Index("ix_pomodoro_user_id_ended_at", "user_id", "ended_at"),
    )


class Timer(SQLModel, table=True):
    """Each User's single persisted Timer row (ADR-0003: server-side, lazily settled).

    `phase_ended_at` records the exact instant the current phase ended (e.g. the
    moment a manual `stop` moved the Timer into `AskingToLog`), independent of
    `accumulated_active_seconds`/`running_since`. A later `log` action (T13) reads
    it as the Pomodoro's `ended_at` rather than substituting whatever `now()`
    happens to be when `log` is actually called. A prior (pre-CES) build had no
    such column and crashed `log` on a NULL read — this migration adds it from the
    start rather than retrofitting it later.
    """

    __tablename__ = "timer"  # pyrefly: ignore[bad-override]

    user_id: int = Field(
        sa_column=sa.Column(sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    )
    phase: str
    # RESTRICT mirrors `pomodoro.task_id`: defense in depth behind the T14 app-level
    # guard that refuses to archive/delete a Task currently in progress.
    task_id: int | None = Field(
        default=None,
        sa_column=sa.Column(sa.ForeignKey("task.id", ondelete="RESTRICT"), nullable=True),
    )
    break_kind: str | None = Field(default=None)
    phase_started_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True)
    )
    accumulated_active_seconds: int = Field(default=0)
    running_since: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True)
    )
    phase_ended_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True)
    )
