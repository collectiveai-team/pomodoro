"""Domain-level errors shared across pomodoro.core.

Carry no HTTP concerns: pomodoro.entrypoints.app maps DomainError (and its
subclasses) to the single ErrorResponse shape via one registered exception
handler, so routers and core rules never construct HTTP responses themselves.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors raised by core domain rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
