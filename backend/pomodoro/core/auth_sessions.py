"""The `AuthSession` entity, opaque session tokens, and its repository Protocol.

The session token itself never touches the database: only its SHA-256 hash is stored, so a
database leak cannot be replayed as a live session. Argon2 is deliberately not used here — it is
reserved for low-entropy, user-chosen passwords (`core.passwords`); a long, cryptographically
random session token has no brute-force surface to slow down.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, NewType, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from pomodoro.core.users import UserId

AuthSessionId = NewType("AuthSessionId", UUID)

SESSION_DURATION = timedelta(days=30)
_TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class AuthSession:
    """A logged-in session: only the hash of its opaque token is ever persisted."""

    id: AuthSessionId
    user_id: UserId
    token_hash: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime


def generate_session_token() -> str:
    """Return a new high-entropy opaque token for a cookie (never stored directly)."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest stored in the database in place of a raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(
    *, session_id: AuthSessionId, user_id: UserId, token_hash: str, now: datetime
) -> AuthSession:
    """Build a freshly issued AuthSession, valid for `SESSION_DURATION` starting at `now`."""
    return AuthSession(
        id=session_id,
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        last_used_at=now,
        expires_at=now + SESSION_DURATION,
    )


class AuthSessionRepository(Protocol):
    """Persistence Protocol for `AuthSession`, implemented by `database.repositories`."""

    def add(self, auth_session: AuthSession) -> None:
        """Persist a newly issued session."""
        ...
