"""DB session provider (ADR-0002): a SQLModel `Session` scoped to one request.

`DbSession` is a Protocol so code outside the database layer can depend on "a database session"
as a dependency-injection seam without importing SQLModel/SQLAlchemy's concrete `Session` type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from sqlmodel import Session

from pomodoro.database.engine import get_engine

if TYPE_CHECKING:
    from collections.abc import Iterator


class DbSession(Protocol):
    """The database session surface usable outside the database layer."""


def get_db_session() -> Iterator[DbSession]:
    """Yield a database session bound to the process-wide engine."""
    with Session(get_engine()) as session:
        yield session
