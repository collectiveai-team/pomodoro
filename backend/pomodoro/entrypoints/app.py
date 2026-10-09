"""FastAPI application factory (ADR-0001): settings, logging, routers, and centralized errors."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exceptions import StarletteHTTPException as HTTPException
from fastapi.responses import JSONResponse

from pomodoro.api.v1.auth.routers import router as auth_router
from pomodoro.api.v1.routers.health import router as health_router
from pomodoro.api.v1.schemas.responses.error import ErrorResponse
from pomodoro.core.logger import get_logger
from pomodoro.core.users import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidPasswordLengthError,
)
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

    @app.exception_handler(InvalidEmailError)
    async def _handle_invalid_email(request: Request, exc: InvalidEmailError) -> JSONResponse:
        log.info("invalid_email", path=request.url.path)
        return _error_response(422, str(exc), "invalid_email")

    @app.exception_handler(DuplicateEmailError)
    async def _handle_duplicate_email(request: Request, exc: DuplicateEmailError) -> JSONResponse:
        log.info("duplicate_email", path=request.url.path)
        return _error_response(422, str(exc), "duplicate_email")

    @app.exception_handler(InvalidPasswordLengthError)
    async def _handle_invalid_password_length(
        request: Request, exc: InvalidPasswordLengthError
    ) -> JSONResponse:
        log.info("invalid_password_length", path=request.url.path)
        return _error_response(422, str(exc), "invalid_password_length")

    @app.exception_handler(InvalidCredentialsError)
    async def _handle_invalid_credentials(
        request: Request, exc: InvalidCredentialsError
    ) -> JSONResponse:
        log.info("invalid_credentials", path=request.url.path)
        return _error_response(401, str(exc), "invalid_credentials")

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
    app.include_router(auth_router, prefix="/api/v1")

    return app


app = create_app()
