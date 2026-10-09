"""SQLModel-backed `core.repositories.AuthSessionRepository` (CES-18, T7).

The only place a `tables.AuthSession` row is mapped to a
`core.entities.AuthSession` dataclass: every method here returns the
dataclass, never the row or a raw dict (CES-79, ADR-0002).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import select

from pomodoro.core.entities import AuthSession, AuthSessionId, UserId
from pomodoro.database import tables
from pomodoro.database.rows import require_id
from pomodoro.database.timestamps import as_utc

if TYPE_CHECKING:
    from datetime import datetime

    from sqlmodel import Session


def _to_entity(row: tables.AuthSession) -> AuthSession:
    return AuthSession(
        id=AuthSessionId(require_id(row.id)),
        user_id=UserId(row.user_id),
        token_hash=row.token_hash,
        created_at=as_utc(row.created_at),
        last_used_at=as_utc(row.last_used_at),
        expires_at=as_utc(row.expires_at),
    )


@dataclass
class SqlAuthSessionRepository:
    """`core.repositories.AuthSessionRepository` implementation over a SQLModel `Session`."""

    _session: Session

    def add(
        self,
        *,
        user_id: UserId,
        token_hash: str,
        created_at: datetime,
        last_used_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        row = tables.AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            created_at=created_at,
            last_used_at=last_used_at,
            expires_at=expires_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_entity(row)

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        row = self._session.exec(
            select(tables.AuthSession).where(tables.AuthSession.token_hash == token_hash)
        ).first()
        return _to_entity(row) if row is not None else None

    def update(self, session: AuthSession) -> AuthSession:
        row = self._session.get(tables.AuthSession, session.id)
        if row is None:
            raise RuntimeError(f"AuthSession {session.id} does not exist.")
        row.last_used_at = session.last_used_at
        row.expires_at = session.expires_at
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_entity(row)

    def delete(self, session_id: AuthSessionId) -> None:
        row = self._session.get(tables.AuthSession, session_id)
        if row is not None:
            self._session.delete(row)
            self._session.commit()

    def delete_all_for_user(self, user_id: UserId) -> None:
        rows = self._session.exec(
            select(tables.AuthSession).where(tables.AuthSession.user_id == user_id)
        ).all()
        for row in rows:
            self._session.delete(row)
        self._session.commit()

    def delete_all_for_user_except(
        self, user_id: UserId, *, keep_session_id: AuthSessionId
    ) -> None:
        rows = self._session.exec(
            select(tables.AuthSession).where(
                tables.AuthSession.user_id == user_id,
                tables.AuthSession.id != keep_session_id,
            )
        ).all()
        for row in rows:
            self._session.delete(row)
        self._session.commit()
