"""The `auth_session` table (ADR-0002 schema): only a session token's hash is ever stored."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class AuthSessionTable(SQLModel, table=True):
    """Persistence row for an `AuthSession`."""

    __tablename__ = "auth_session"  # pyrefly: ignore[bad-override]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
