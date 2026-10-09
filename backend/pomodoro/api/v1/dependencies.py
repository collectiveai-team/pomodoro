"""Typed `Depends(...)` anchors for state `api` needs but may not build itself (T9).

`api` sits below `entrypoints` in the CES-5 layer contract (`entrypoints -> api ->
database -> core`), so it can never import `pomodoro.entrypoints.dependencies` -
the module that actually resolves `Settings` and builds the database engine.
These functions exist only as stable references for router `Depends(...)`
parameters; `entrypoints.app.create_app()` installs the real implementations via
`app.dependency_overrides` before the app serves a single request, so the
`NotImplementedError` below would only ever fire if that wiring were itself
broken - never during normal request handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlmodel import Session

    from pomodoro.core.entities import AuthSession
    from pomodoro.core.rate_limit import RateLimiter

_NOT_WIRED = "entrypoints.app.create_app() did not override this dependency."


def get_db_session() -> Iterator[Session]:
    """Overridden with `entrypoints.dependencies.get_db_session`."""
    raise NotImplementedError(_NOT_WIRED)


def get_rate_limiter() -> RateLimiter:
    """Overridden with `entrypoints.dependencies.get_rate_limiter`."""
    raise NotImplementedError(_NOT_WIRED)


def require_session() -> AuthSession:
    """Overridden with `entrypoints.dependencies.require_session`."""
    raise NotImplementedError(_NOT_WIRED)


def get_trust_forwarded_for() -> bool:
    """Overridden with `entrypoints.dependencies.get_trust_forwarded_for`."""
    raise NotImplementedError(_NOT_WIRED)
