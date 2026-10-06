"""Regression tests for the login rate limiter behind the frontend's proxy.

`api.auth._rate_limit_key` keys the login/register rate limiter on
`request.client.host` plus the normalized email (story 12: by IP + email).
Every request reaches the backend through the Next.js frontend's rewrite
(`frontend/proxy.ts`), and Next forwards a client-supplied `X-Forwarded-For`
untouched (it only fills the header in when it is absent). Trusting that
header from the frontend therefore lets any caller choose a fresh bucket per
request, so the limiter never fires.

The backend image keeps uvicorn's default proxy trust (127.0.0.1 only), so a
forged `X-Forwarded-For` arriving from any other peer is ignored and repeated
failures for one account are still refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from tests.conftest import authed_session as _authed_session

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.unit
def test_forged_forwarded_for_cannot_bypass_login_rate_limit(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    # uvicorn's default trust, as the backend image runs it: only 127.0.0.1.
    default_trust_client = TestClient(
        ProxyHeadersMiddleware(s.client.app, trusted_hosts="127.0.0.1")  # type: ignore[arg-type]
    )

    def attempt(forwarded_for: str) -> int:
        return default_trust_client.post(
            "/api/auth/login",
            json={"email": "person@example.com", "password": "wrong password"},
            headers={"X-Forwarded-For": forwarded_for},
        ).status_code

    # A fresh forged address on every try must not reset the bucket.
    for i in range(5):
        assert attempt(f"198.51.100.{i}") == 401
    assert attempt("198.51.100.99") == 429


@pytest.mark.unit
def test_backend_image_does_not_trust_forwarded_headers_from_any_peer() -> None:
    """Guards against re-adding the blanket trust that made the bypass possible."""
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text()
    cmd = next(line for line in dockerfile.splitlines() if line.startswith('CMD ["uvicorn"'))
    assert "--forwarded-allow-ips" not in cmd
