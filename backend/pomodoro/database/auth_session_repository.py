"""SQLModel-backed `AuthSessionRepository` Protocol implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from pomodoro.core.entities import AuthSession, AuthSessionId, UserId
from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.engine import Engine

    from pomodoro.core.clock import Clock


def _to_entity(row: tables.AuthSession) -> AuthSession:
    if row.id is None:
        raise AssertionError
    return AuthSession(
        id=AuthSessionId(row.id),
        user_id=UserId(row.user_id),
        token_hash=row.token_hash,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
    )


class SQLAuthSessionRepository:
    """`AuthSessionRepository` Protocol implementation backed by a SQLModel engine.

    Owns a `Clock` because `create`'s and `touch_last_used`'s timestamps are a
    persistence-time concern, unlike other entities whose `created_at` is set
    by the caller before the repository ever sees them.
    """

    def __init__(self, engine: Engine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    def create(self, user_id: UserId, token_hash: str, expires_at: datetime) -> AuthSession:
        now = self._clock.now()
        with session_scope(self._engine) as session:
            row = tables.AuthSession(
                user_id=user_id,
                token_hash=token_hash,
                created_at=now,
                last_used_at=now,
                expires_at=expires_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_entity(row)

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        with session_scope(self._engine) as session:
            row = session.exec(
                select(tables.AuthSession).where(tables.AuthSession.token_hash == token_hash)
            ).first()
            return _to_entity(row) if row is not None else None

    def touch_last_used(self, session_id: AuthSessionId) -> None:
        with session_scope(self._engine) as session:
            row = session.get(tables.AuthSession, session_id)
            if row is not None:
                row.last_used_at = self._clock.now()
                session.add(row)
                session.commit()

    def revoke(self, session_id: AuthSessionId) -> None:
        with session_scope(self._engine) as session:
            row = session.get(tables.AuthSession, session_id)
            if row is not None:
                session.delete(row)
                session.commit()

    def revoke_all_for_user(self, user_id: UserId) -> None:
        with session_scope(self._engine) as session:
            rows = session.exec(
                select(tables.AuthSession).where(tables.AuthSession.user_id == user_id)
            ).all()
            for row in rows:
                session.delete(row)
            session.commit()
