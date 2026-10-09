"""The FastAPI app factory: construction, the domain-error handler, router wiring.

Per `api-structure`: this module owns app construction and router registration
only. Route handlers stay thin and delegate to core/database; no business logic
lives here.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from pomodoro.api.v1 import dependencies as api_dependencies
from pomodoro.api.v1.routers import auth, health, tags, tasks
from pomodoro.api.v1.schemas.responses.errors import ErrorResponse
from pomodoro.core.errors import DomainError
from pomodoro.core.logger import get_logger
from pomodoro.entrypoints.dependencies import (
    get_db_session,
    get_rate_limiter,
    get_trust_forwarded_for,
    require_session,
)

log = get_logger(__name__)


def create_app() -> FastAPI:
    """Build the FastAPI app: the single domain-error handler, then versioned routers."""
    app = FastAPI(title="Pomodoro Collective")

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        log.info("domain_error", path=request.url.path, detail=exc.message)
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(detail=exc.message).model_dump(),
        )

    # `api` sits below `entrypoints` in the import-linter layer contract (CES-5), so it may
    # never import `entrypoints.dependencies` directly. Routers depend on the typed
    # placeholders in `api.v1.dependencies` instead; this is the one place (the app factory)
    # allowed to wire them to their real implementations.
    app.dependency_overrides[api_dependencies.get_db_session] = get_db_session
    app.dependency_overrides[api_dependencies.get_rate_limiter] = get_rate_limiter
    app.dependency_overrides[api_dependencies.require_session] = require_session
    app.dependency_overrides[api_dependencies.get_trust_forwarded_for] = get_trust_forwarded_for

    # The health route's DB-session dependency is wired here, not inside
    # `api.v1.routers.health`, for the same reason.
    app.include_router(
        health.router,
        prefix="/api/v1",
        dependencies=[Depends(get_db_session)],
    )
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(tags.router, prefix="/api/v1")

    return app


app = create_app()
