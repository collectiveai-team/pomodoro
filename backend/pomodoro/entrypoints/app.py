"""The FastAPI app factory: construction, the domain-error handler, router wiring.

Per `api-structure`: this module owns app construction and router registration
only. Route handlers stay thin and delegate to core/database; no business logic
lives here.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from pomodoro.api.v1.routers import health
from pomodoro.api.v1.schemas.responses.errors import ErrorResponse
from pomodoro.core.errors import DomainError
from pomodoro.core.logger import get_logger
from pomodoro.entrypoints.dependencies import get_db_session

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

    # The health route's DB-session dependency is wired here, not inside
    # `api.v1.routers.health`: `api` sits below `entrypoints` in the import-linter
    # layer contract (CES-5), so it may never import `entrypoints.dependencies`.
    app.include_router(
        health.router,
        prefix="/api/v1",
        dependencies=[Depends(get_db_session)],
    )

    return app


app = create_app()
