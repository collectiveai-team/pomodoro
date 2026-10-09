"""FastAPI application factory (ADR-0001): settings, logging, routers, and centralized errors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exceptions import StarletteHTTPException as HTTPException
from fastapi.responses import JSONResponse

from pomodoro.api.v1.auth.rate_limit import InMemoryRateLimiter, RateLimitExceededError
from pomodoro.api.v1.auth.routers import router as auth_router
from pomodoro.api.v1.routers.health import router as health_router
from pomodoro.api.v1.schemas.responses.error import ErrorResponse
from pomodoro.api.v1.tasks.routers import router as tasks_router
from pomodoro.core.logger import get_logger
from pomodoro.core.tasks import (
    DuplicateTaskTextError,
    EmptyTaskTextError,
    TaskHasRecordedPomodorosError,
    TaskNotFoundError,
    TaskReorderMismatchError,
    TaskTextTooLongError,
)
from pomodoro.core.users import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidPasswordLengthError,
)
from pomodoro.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = get_logger(__name__)


def _error_response(status_code: int, detail: str, code: str) -> JSONResponse:
    body = ErrorResponse(detail=detail, code=code)
    return JSONResponse(status_code=status_code, content=body.model_dump())


# Domain errors that all map to the same shape: a fixed status code and error `code`, logged
# under that same `code` as the event name. `HTTPException`, `RequestValidationError`, and the
# unhandled-`Exception` fallback each need their own logic (a dynamic status code, or extra
# fields), so they stay as explicit handlers below instead of joining this table.
_DOMAIN_ERROR_HANDLERS: list[tuple[type[Exception], int, str]] = [
    (InvalidEmailError, 422, "invalid_email"),
    (DuplicateEmailError, 422, "duplicate_email"),
    (InvalidPasswordLengthError, 422, "invalid_password_length"),
    (InvalidCredentialsError, 401, "invalid_credentials"),
    (RateLimitExceededError, 429, "rate_limited"),
    (EmptyTaskTextError, 422, "empty_task_text"),
    (TaskTextTooLongError, 422, "task_text_too_long"),
    (DuplicateTaskTextError, 422, "duplicate_task_text"),
    (TaskNotFoundError, 404, "task_not_found"),
    (TaskReorderMismatchError, 422, "task_reorder_mismatch"),
    (TaskHasRecordedPomodorosError, 409, "task_has_recorded_pomodoros"),
]


def _make_domain_error_handler(
    status_code: int, code: str
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def _handle(request: Request, exc: Exception) -> JSONResponse:
        log.info(code, path=request.url.path)
        return _error_response(status_code, str(exc), code)

    return _handle


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

    for exc_type, status_code, code in _DOMAIN_ERROR_HANDLERS:
        app.add_exception_handler(exc_type, _make_domain_error_handler(status_code, code))

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", path=request.url.path, exc_info=exc)
        return _error_response(500, "Internal server error.", "internal_error")


def create_app() -> FastAPI:
    """Build the FastAPI application: routers, dependency providers, and error handlers."""
    settings = get_settings()
    app = FastAPI(title="Pomodoro Collective", debug=settings.debug)
    app.state.rate_limiter = InMemoryRateLimiter()

    _register_exception_handlers(app)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")

    return app


app = create_app()
