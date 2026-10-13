"""SQLModel implementation of `UserRepository` (ADR-0002)."""

from __future__ import annotations

from fastapi import Depends
from sqlmodel import Session, select

from pomodoro.core.users import User, UserCredentials, UserId, UserRepository
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

    def get_by_id(self, user_id: UserId) -> User | None:
        """Return the User with this id, or None."""
        row = self._session.get(UserTable, user_id)
        return None if row is None else _to_entity(row)

    def get_credentials_by_email_key(self, email_key: str) -> UserCredentials | None:
        """Return the User and stored password hash whose `email_key` matches, or None."""
        row = self._session.exec(select(UserTable).where(UserTable.email_key == email_key)).first()
        if row is None:
            return None
        return UserCredentials(user=_to_entity(row), password_hash=row.password_hash)

    def update_preferences(
        self,
        user_id: UserId,
        *,
        alarm_enabled: bool,
        notifications_enabled: bool,
        time_zone: str,
    ) -> None:
        """Overwrite the `user` row's preference columns and commit."""
        row = self._session.get(UserTable, user_id)
        if row is None:
            return
        row.alarm_enabled = alarm_enabled
        row.notifications_enabled = notifications_enabled
        row.time_zone = time_zone
        self._session.add(row)
        self._session.commit()

    def get_credentials_by_id(self, user_id: UserId) -> UserCredentials | None:
        """Return the User and stored password hash whose id matches, or None."""
        row = self._session.get(UserTable, user_id)
        if row is None:
            return None
        return UserCredentials(user=_to_entity(row), password_hash=row.password_hash)

    def update_password(self, user_id: UserId, password_hash: str) -> None:
        """Overwrite the `user` row's password hash and commit."""
        row = self._session.get(UserTable, user_id)
        if row is None:
            return
        row.password_hash = password_hash
        self._session.add(row)
        self._session.commit()

    def delete(self, user_id: UserId) -> None:
        """Delete the `user` row; FK `ON DELETE CASCADE`/`RESTRICT` handle every owned table."""
        row = self._session.get(UserTable, user_id)
        if row is None:
            return
        self._session.delete(row)
        self._session.commit()


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
