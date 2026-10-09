"""CES-76 · the one place backend env/flags are read (pydantic-settings).

Every other module reaches configuration through the cached `get_settings()`
below — never `os.getenv`/`os.environ` directly (ast-grep flags that outside
this module; `core/logger.py` carries a documented, visible exception for its
own bootstrap-time `ENV`/`LOG_LEVEL` reads).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend application settings, bound from environment variables.

    Field names map directly onto their env var names (`database_url` <->
    `DATABASE_URL`): no app-specific prefix, since this project is the only
    consumer of its own process environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./pomodoro.db")
    # Opt-in trust of `X-Forwarded-For` for client-IP resolution (T8 rate limiting). Off by
    # default: a prior build let `--forwarded-allow-ips=*` make the IP dimension
    # attacker-controlled, defeating the rate limiter outright. Only flip this on behind a
    # real, configured edge proxy (see backend/Dockerfile's deploy notes, T30).
    trust_forwarded_for: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, constructed (and validated) once."""
    return Settings()
