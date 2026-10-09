"""Real FastAPI dependency providers, wired in the app factory (never stubs)."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from sqlmodel import Session

from pomodoro.database.engine import build_engine
from pomodoro.entrypoints.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide engine, built once from the configured database URL."""
    return build_engine(get_settings().database_url)


def get_db_session() -> Iterator[Session]:
    """Yield a SQLModel session bound to the configured engine, closing it after the request."""
    with Session(get_engine()) as session:
        yield session
