"""Session cookie, CSRF guard, client-IP and rate-limit helpers shared by `api/v1` (T8).

These are framework-touching (unlike `core`) but carry no business rules of
their own and no database access — `entrypoints.dependencies.require_session`
composes them with `SqlAuthSessionRepository` (T7) to turn a request's cookie
into a resolved `AuthSession`. Keeping them here, not duplicated per router,
means every future `api/v1` router (auth, tasks, ...) shares one cookie shape,
one CSRF rule and one IP-resolution rule (issue #12 spec).
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, Response, status

if TYPE_CHECKING:
    from datetime import datetime

    from pomodoro.core.rate_limit import RateLimiter

SESSION_COOKIE_NAME = "session"
SESSION_COOKIE_PATH = "/"
SESSION_TTL = timedelta(days=30)
# Sliding-expiry write granularity: `require_session` only persists a renewed
# `last_used_at`/`expires_at` once this much time has passed since the last write, so an
# active User's session doesn't trigger a database write on every single request.
SESSION_RENEWAL_THRESHOLD = timedelta(hours=1)

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_JSON_CONTENT_TYPE = "application/json"


def get_session_token(request: Request) -> str | None:
    """Return the raw session token from the request cookie, or `None` if absent."""
    return request.cookies.get(SESSION_COOKIE_NAME)


def set_session_cookie(response: Response, *, token: str) -> None:
    """Set the `HttpOnly; Secure; SameSite=Lax; Path=/` session cookie (issue #12 spec)."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie (logout, issue #12 spec)."""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path=SESSION_COOKIE_PATH)


def require_json_content_type(request: Request) -> None:
    """CSRF guard (issue #12 spec): every mutation must declare `Content-Type: application/json`.

    Combined with the cookie's `SameSite=Lax`, a cross-site HTML form (whose
    browser-set request content types are never `application/json`) can never
    trigger a state-changing request against this API.
    """
    if request.method not in _MUTATING_METHODS:
        return
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != _JSON_CONTENT_TYPE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mutating requests must send Content-Type: application/json.",
        )


def resolve_client_ip(request: Request, *, trust_forwarded_for: bool) -> str:
    """Return the IP to rate-limit on: the real connecting peer unless proxy trust is explicit.

    Regression guard: a prior build trusted `X-Forwarded-For` unconditionally, so a
    `--forwarded-allow-ips=*` uvicorn flag let an attacker spoof the IP dimension and
    defeat the rate limiter outright. The header is only consulted when
    `trust_forwarded_for` is explicitly enabled (`Settings.trust_forwarded_for`).
    """
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client is not None else "unknown"


def enforce_login_rate_limit(
    limiter: RateLimiter, *, ip: str, email_key: str, now: datetime
) -> None:
    """Raise 429 once `(ip, email_key)` has hit `rate_limit.MAX_FAILED_ATTEMPTS`."""
    if limiter.is_blocked(ip=ip, email_key=email_key, now=now):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
        )
