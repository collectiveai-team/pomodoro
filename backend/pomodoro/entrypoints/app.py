"""FastAPI application factory (ADR-0001): settings, logging, routers, and centralized errors."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exceptions import StarletteHTTPException as HTTPException
from fastapi.responses import JSONResponse

from pomodoro.api.v1.routers.health import router as health_router
from pomodoro.api.v1.schemas.responses.error import ErrorResponse
from pomodoro.core.logger import get_logger
from pomodoro.settings import get_settings

log = get_logger(__name__)


def _error_response(status_code: int, detail: str, code: str) -> JSONResponse:
    body = ErrorResponse(detail=detail, code=code)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        log.info("request_validation_error", path=request.url.path, errors=exc.errors())
        return _error_response(422, "Invalid request.", "validation_error")

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        log.info("http_exception", path=request.url.path, status_code=exc.status_code)
        return _error_response(exc.status_code, str(exc.detail), "http_error")

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", path=request.url.path, exc_info=exc)
        return _error_response(500, "Internal server error.", "internal_error")


def create_app() -> FastAPI:
    """Build the FastAPI application: routers, dependency providers, and error handlers."""
    settings = get_settings()
    app = FastAPI(title="Pomodoro Collective", debug=settings.debug)

    _register_exception_handlers(app)
    app.include_router(health_router, prefix="/api")

    return app


app = create_app()
