"""The `user` table (ADR-0002 schema). SQLModel rows never leave the `database` layer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class UserTable(SQLModel, table=True):
    """Persistence row for a `User`: adds `password_hash`, absent from the core entity."""

    __tablename__ = "user"  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str
    email_key: str = Field(unique=True, index=True)
    password_hash: str
    time_zone: str
    alarm_enabled: bool = Field(default=True)
    notifications_enabled: bool = Field(default=False)
    created_at: datetime
