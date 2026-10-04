"""SQLModel-backed `UserRepository` Protocol implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from pomodoro.core.auth import UserRecord
from pomodoro.core.entities import User, UserId
from pomodoro.database import tables
from pomodoro.database.engine import session_scope

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def _to_entity(row: tables.User) -> User:
    if row.id is None:
        raise AssertionError
    return User(
        id=UserId(row.id),
        email=row.email,
        email_key=row.email_key,
        created_at=row.created_at,
        time_zone=row.time_zone,
        alarm_enabled=row.alarm_enabled,
        notifications_enabled=row.notifications_enabled,
    )


class SQLUserRepository:
    """`UserRepository` Protocol implementation backed by a SQLModel engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_by_id(self, user_id: UserId) -> User | None:
        with session_scope(self._engine) as session:
            row = session.get(tables.User, user_id)
            return _to_entity(row) if row is not None else None

    def get_by_email_key(self, email_key: str) -> UserRecord | None:
        with session_scope(self._engine) as session:
            row = session.exec(
                select(tables.User).where(tables.User.email_key == email_key)
            ).first()
            if row is None:
                return None
            return UserRecord(user=_to_entity(row), password_hash=row.password_hash)

    def add(self, user: User, password_hash: str) -> User:
        with session_scope(self._engine) as session:
            row = tables.User(
                email=user.email,
                email_key=user.email_key,
                password_hash=password_hash,
                time_zone=user.time_zone,
                alarm_enabled=user.alarm_enabled,
                notifications_enabled=user.notifications_enabled,
                created_at=user.created_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_entity(row)

    def update(self, user: User) -> User:
        with session_scope(self._engine) as session:
            row = session.get(tables.User, user.id)
            if row is None:
                raise LookupError(f"User {user.id} does not exist")
            row.email = user.email
            row.email_key = user.email_key
            row.time_zone = user.time_zone
            row.alarm_enabled = user.alarm_enabled
            row.notifications_enabled = user.notifications_enabled
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_entity(row)

    def delete(self, user_id: UserId) -> None:
        with session_scope(self._engine) as session:
            row = session.get(tables.User, user_id)
            if row is not None:
                session.delete(row)
                session.commit()
