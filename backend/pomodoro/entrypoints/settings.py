"""Runtime settings, sourced from process environment variables.

The shape and local default of each variable is documented in `.env.schema` at the
repository root; varlock loads it into the process environment in deployment. A
bare `uvicorn`/test run falls back to the same default declared there.
"""

import os
from dataclasses import dataclass

DEFAULT_DATABASE_URL = "sqlite:///.tmp/pomodoro.db"


@dataclass(frozen=True)
class Settings:
    """Process-wide configuration resolved once at startup."""

    database_url: str


def get_settings() -> Settings:
    """Read settings from the environment, falling back to local defaults."""
    return Settings(database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
