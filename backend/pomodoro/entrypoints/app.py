"""The FastAPI app factory and the bootable uvicorn entrypoint."""

import uvicorn
from fastapi import FastAPI

from pomodoro.api.auth import RateLimiter, get_login_rate_limiter, get_register_rate_limiter
from pomodoro.api.auth import router as auth_router
from pomodoro.api.health import get_clock as get_health_clock
from pomodoro.api.health import router as health_router
from pomodoro.api.session import csrf_guard
from pomodoro.api.session import get_auth_session_repository as get_session_repo_dependency
from pomodoro.api.session import get_clock as get_session_clock
from pomodoro.api.session import get_user_repository as get_user_repo_dependency
from pomodoro.api.tags import router as tags_router
from pomodoro.api.tasks import get_pomodoro_repository as get_pomodoro_repo_dependency
from pomodoro.api.tasks import get_tag_repository as get_tag_repo_dependency
from pomodoro.api.tasks import get_task_repository as get_task_repo_dependency
from pomodoro.api.tasks import get_timer_repository as get_timer_repo_dependency
from pomodoro.api.tasks import router as tasks_router
from pomodoro.api.timer import router as timer_router
from pomodoro.database.auth_session_repository import SQLAuthSessionRepository
from pomodoro.database.engine import create_db_engine
from pomodoro.database.pomodoro_repository import SQLPomodoroRepository
from pomodoro.database.tag_repository import SQLTagRepository
from pomodoro.database.task_repository import SQLTaskRepository
from pomodoro.database.timer_repository import SQLTimerRepository
from pomodoro.database.user_repository import SQLUserRepository
from pomodoro.entrypoints.clock import RealClock
from pomodoro.entrypoints.settings import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI app with real dependencies wired in.

    `require_session` is depended on directly by the `auth` router's
    session-scoped endpoints (logout/me/change-password/delete-account); every
    later non-auth router will depend on it the same way.
    """
    app = FastAPI(title="Pomodoro Collective API")
    app.state.settings = get_settings()
    app.state.engine = create_db_engine(app.state.settings.database_url)
    app.state.login_rate_limiter = RateLimiter()
    app.state.register_rate_limiter = RateLimiter()
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(tasks_router)
    app.include_router(tags_router)
    app.include_router(timer_router)
    app.dependency_overrides[get_health_clock] = RealClock
    app.dependency_overrides[get_session_clock] = RealClock
    app.dependency_overrides[get_user_repo_dependency] = lambda: SQLUserRepository(app.state.engine)
    app.dependency_overrides[get_session_repo_dependency] = lambda: SQLAuthSessionRepository(
        app.state.engine, RealClock()
    )
    app.dependency_overrides[get_login_rate_limiter] = lambda: app.state.login_rate_limiter
    app.dependency_overrides[get_register_rate_limiter] = lambda: app.state.register_rate_limiter
    app.dependency_overrides[get_task_repo_dependency] = lambda: SQLTaskRepository(app.state.engine)
    app.dependency_overrides[get_tag_repo_dependency] = lambda: SQLTagRepository(app.state.engine)
    app.dependency_overrides[get_pomodoro_repo_dependency] = lambda: SQLPomodoroRepository(
        app.state.engine
    )
    app.dependency_overrides[get_timer_repo_dependency] = lambda: SQLTimerRepository(
        app.state.engine
    )
    app.middleware("http")(csrf_guard)
    return app


app = create_app()


def main() -> None:
    """Run the app under uvicorn; the `pomodoro-api` console-script entrypoint."""
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
