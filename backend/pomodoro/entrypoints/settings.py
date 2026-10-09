"""CES-76 · the one place env/flags are read for the backend.

Everything else reaches configuration through :func:`get_settings`, never ``os.getenv`` /
``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, constructed (and validated) once."""
    return Settings()
