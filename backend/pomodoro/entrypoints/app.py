"""The FastAPI app factory and the bootable uvicorn entrypoint."""

import uvicorn
from fastapi import FastAPI

from pomodoro.api.health import get_clock as get_health_clock
from pomodoro.api.health import router as health_router
from pomodoro.api.session import csrf_guard
from pomodoro.api.session import get_auth_session_repository as get_session_repo_dependency
from pomodoro.api.session import get_clock as get_session_clock
from pomodoro.api.session import get_user_repository as get_user_repo_dependency
from pomodoro.database.auth_session_repository import SQLAuthSessionRepository
from pomodoro.database.engine import create_db_engine
from pomodoro.database.user_repository import SQLUserRepository
from pomodoro.entrypoints.clock import RealClock
from pomodoro.entrypoints.settings import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI app with real dependencies wired in.

    `require_session` (used by every later non-auth router) is wired here so
    those routers only need to depend on it; no router using it is mounted yet
    beyond `health`.
    """
    app = FastAPI(title="Pomodoro Collective API")
    app.state.settings = get_settings()
    app.state.engine = create_db_engine(app.state.settings.database_url)
    app.include_router(health_router)
    app.dependency_overrides[get_health_clock] = RealClock
    app.dependency_overrides[get_session_clock] = RealClock
    app.dependency_overrides[get_user_repo_dependency] = lambda: SQLUserRepository(app.state.engine)
    app.dependency_overrides[get_session_repo_dependency] = lambda: SQLAuthSessionRepository(
        app.state.engine, RealClock()
    )
    app.middleware("http")(csrf_guard)
    return app


app = create_app()


def main() -> None:
    """Run the app under uvicorn; the `pomodoro-api` console-script entrypoint."""
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
