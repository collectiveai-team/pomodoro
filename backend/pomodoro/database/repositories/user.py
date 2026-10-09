"""SQLModel implementation of `UserRepository` (ADR-0002)."""

from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session, select

from pomodoro.core.users import User, UserId, UserRepository
from pomodoro.database.models.user import UserTable
from pomodoro.database.session import get_db_session


class SqlUserRepository:
    """`UserRepository` backed by the `user` SQLModel table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User, password_hash: str) -> None:
        """Insert a new `user` row and commit."""
        self._session.add(
            UserTable(
                id=user.id,
                email=user.email,
                email_key=user.email_key,
                password_hash=password_hash,
                time_zone=user.time_zone,
                alarm_enabled=user.alarm_enabled,
                notifications_enabled=user.notifications_enabled,
                created_at=user.created_at,
            )
        )
        self._session.commit()

    def get_by_email_key(self, email_key: str) -> User | None:
        """Return the User whose `email_key` matches, or None."""
        row = self._session.exec(select(UserTable).where(UserTable.email_key == email_key)).first()
        return None if row is None else _to_entity(row)


def _to_entity(row: UserTable) -> User:
    return User(
        id=UserId(row.id),
        email=row.email,
        email_key=row.email_key,
        time_zone=row.time_zone,
        alarm_enabled=row.alarm_enabled,
        notifications_enabled=row.notifications_enabled,
        created_at=row.created_at,
    )


def get_user_repository(session: Session = Depends(get_db_session)) -> UserRepository:
    """FastAPI provider: a `UserRepository` backed by the request's DB session."""
    return SqlUserRepository(session)
