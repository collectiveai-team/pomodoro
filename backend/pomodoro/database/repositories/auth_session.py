"""SQLModel implementation of `AuthSessionRepository` (ADR-0002)."""

from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session

from pomodoro.core.auth_sessions import AuthSession, AuthSessionRepository
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


def get_auth_session_repository(
    session: Session = Depends(get_db_session),
) -> AuthSessionRepository:
    """FastAPI provider: an `AuthSessionRepository` backed by the request's DB session."""
    return SqlAuthSessionRepository(session)
