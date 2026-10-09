"""DB session provider.

Placeholder until the real SQLModel engine/session lands (a later ticket): it yields ``None``
rather than raising, so the app factory can wire a genuine FastAPI dependency now and routes can
depend on "a session" without every caller special-casing "not built yet".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def get_db_session() -> Iterator[None]:
    """Yield a placeholder DB session (no real connection exists yet)."""
    yield None
