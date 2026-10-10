"""SQLModel implementation of `AuthSessionRepository` (ADR-0002)."""

from __future__ import annotations

from datetime import datetime

from fastapi import Depends
from sqlmodel import Session, select

from pomodoro.core.auth_sessions import (
    SESSION_DURATION,
    AuthSession,
    AuthSessionId,
    AuthSessionRepository,
)
from pomodoro.core.users import UserId
from pomodoro.database.models.auth_session import AuthSessionTable
from pomodoro.database.session import get_db_session


class SqlAuthSessionRepository:
    """`AuthSessionRepository` backed by the `auth_session` SQLModel table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, auth_session: AuthSession) -> None:
        """Insert a new `auth_session` row and commit."""
        self._session.add(
            AuthSessionTable(
                id=auth_session.id,
                user_id=auth_session.user_id,
                token_hash=auth_session.token_hash,
                created_at=auth_session.created_at,
                last_used_at=auth_session.last_used_at,
                expires_at=auth_session.expires_at,
            )
        )
        self._session.commit()

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """Return the session whose `token_hash` matches, or None."""
        row = self._session.exec(
            select(AuthSessionTable).where(AuthSessionTable.token_hash == token_hash)
        ).first()
        return None if row is None else _to_entity(row)

    def touch(self, session_id: AuthSessionId, now: datetime) -> None:
        """Renew a session's sliding expiry: `last_used_at` and `expires_at` from `now`."""
        row = self._session.get(AuthSessionTable, session_id)
        if row is None:
            return
        row.last_used_at = now
        row.expires_at = now + SESSION_DURATION
        self._session.add(row)
        self._session.commit()

    def revoke(self, session_id: AuthSessionId) -> None:
        """Delete the session row; its cookie stops authenticating immediately."""
        row = self._session.get(AuthSessionTable, session_id)
        if row is not None:
            self._session.delete(row)
            self._session.commit()

    def revoke_all_except(self, user_id: UserId, keep_session_id: AuthSessionId) -> None:
        """Delete every session row for `user_id` other than `keep_session_id`, then commit."""
        rows = self._session.exec(
            select(AuthSessionTable).where(
                AuthSessionTable.user_id == user_id,
                AuthSessionTable.id != keep_session_id,
            )
        ).all()
        for row in rows:
            self._session.delete(row)
        self._session.commit()


def _to_entity(row: AuthSessionTable) -> AuthSession:
    return AuthSession(
        id=AuthSessionId(row.id),
        user_id=UserId(row.user_id),
        token_hash=row.token_hash,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
    )


def get_auth_session_repository(
    session: Session = Depends(get_db_session),
) -> AuthSessionRepository:
    """FastAPI provider: an `AuthSessionRepository` backed by the request's DB session."""
    return SqlAuthSessionRepository(session)
