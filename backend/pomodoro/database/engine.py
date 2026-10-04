"""Engine and session factory selecting SQLite or PostgreSQL from `DATABASE_URL`."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy import event
from sqlmodel import Session, create_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

DEFAULT_DATABASE_URL = "sqlite:///.tmp/pomodoro.db"


def create_db_engine(database_url: str = DEFAULT_DATABASE_URL) -> Engine:
    """Build the SQLAlchemy engine for `database_url`.

    SQLite connections get `PRAGMA foreign_keys = ON` enabled on every new
    DBAPI connection; PostgreSQL enforces foreign keys unconditionally.
    """
    engine = create_engine(database_url)
    if database_url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(
        dbapi_connection: sqlite3.Connection, _connection_record: object
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Yield a `Session` bound to `engine`, for request-scoped or test use."""
    with Session(engine) as session:
        yield session
