"""Pomodoro timer backend.

Layered per ADR-0001: ``entrypoints`` -> ``api`` -> ``database`` -> ``core``. The domain model
lands feature-by-feature in later tickets; this package currently carries the house skeleton
(settings, logging, the error envelope, and the app factory) only.
"""

__all__: list[str] = []
