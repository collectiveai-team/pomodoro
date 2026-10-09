"""SQLModel-backed `core.repositories.UserRepository` (CES-18, T7).

The only place a `tables.User` row is mapped to a `core.entities.User`
dataclass: every method here returns the dataclass, never the row or a raw
dict (CES-79, ADR-0002). `password_hash` never appears on the returned `User`;
callers that need it ask `get_password_hash` explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from pomodoro.core.entities import User, UserId
from pomodoro.core.errors import DuplicateEmailError
from pomodoro.core.normalization import user_email_key
from pomodoro.database import tables
from pomodoro.database.rows import require_id
from pomodoro.database.timestamps import as_utc

if TYPE_CHECKING:
    from datetime import datetime

    from sqlmodel import Session


def _to_entity(row: tables.User) -> User:
    return User(
        id=UserId(require_id(row.id)),
        email=row.email,
        created_at=as_utc(row.created_at),
        time_zone=row.time_zone,
        alarm_enabled=row.alarm_enabled,
        notifications_enabled=row.notifications_enabled,
    )


@dataclass
class SqlUserRepository:
    """`core.repositories.UserRepository` implementation over a SQLModel `Session`."""

    _session: Session

    def add(self, *, email: str, password_hash: str, time_zone: str, created_at: datetime) -> User:
        row = tables.User(
            email=email,
            email_key=user_email_key(email),
            password_hash=password_hash,
            time_zone=time_zone,
            created_at=created_at,
        )
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateEmailError(email) from exc
        self._session.refresh(row)
        return _to_entity(row)

    def get_by_id(self, user_id: UserId) -> User | None:
        row = self._session.get(tables.User, user_id)
        return _to_entity(row) if row is not None else None

    def get_by_email(self, email: str) -> User | None:
        row = self._session.exec(
            select(tables.User).where(tables.User.email_key == user_email_key(email))
        ).first()
        return _to_entity(row) if row is not None else None

    def get_password_hash(self, user_id: UserId) -> str | None:
        row = self._session.get(tables.User, user_id)
        return row.password_hash if row is not None else None

    def update(self, user: User) -> User:
        row = self._session.get(tables.User, user.id)
        if row is None:
            raise RuntimeError(f"User {user.id} does not exist.")
        row.time_zone = user.time_zone
        row.alarm_enabled = user.alarm_enabled
        row.notifications_enabled = user.notifications_enabled
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_entity(row)

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None:
        row = self._session.get(tables.User, user_id)
        if row is None:
            raise RuntimeError(f"User {user_id} does not exist.")
        row.password_hash = password_hash
        self._session.add(row)
        self._session.commit()

    def delete(self, user_id: UserId) -> None:
        row = self._session.get(tables.User, user_id)
        if row is not None:
            self._session.delete(row)
            self._session.commit()
