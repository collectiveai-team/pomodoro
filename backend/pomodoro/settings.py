"""CES-76 · the one place env/flags are read for the backend.

Lives at the package root rather than inside `entrypoints` (CES-5): the `database` layer needs
`database_url` too, and `entrypoints` is above `database` in the layer direction, so nesting
settings there would make reading it from `database` an upward (forbidden) import. Everything
else reaches configuration through :func:`get_settings`, never ``os.getenv`` /
``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide backend configuration, read case-insensitively from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="POMODORO_",
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    debug: bool = False
    log_level: str = "INFO"
    # ADR-0002: SQLite locally, PostgreSQL in production, both via the same engine code path
    # (`pomodoro.database.engine.build_engine`).
    database_url: str = Field(default="sqlite:///backend/.tmp/pomodoro.db")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, constructed (and validated) once."""
    return Settings()
