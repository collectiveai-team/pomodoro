"""Regression test for the rate limiter's per-IP key collapsing behind the proxy.

`api.auth._rate_limit_key` keys the login/register rate limiter on
`request.client.host` plus the normalized email (story 12: by IP + email). In
the deployment topology ADR-0001 mandates, every request reaches the backend
from the Next.js frontend's server-side rewrite (`frontend/proxy.ts`), so
`request.client.host` is constant -- the per-IP component is lost and the
limiter degenerates into an account-lockout primitive.

uvicorn's `ProxyHeadersMiddleware` is what could recover the real client from
`X-Forwarded-For`, but it only honors that header from a *trusted* peer, and
defaulted to trusting only `127.0.0.1`. `backend/Dockerfile`'s CMD now passes
`--forwarded-allow-ips=*`, which is safe specifically because this container
publishes no port: the frontend's rewrite is the only peer that can ever
reach it. This test wires the same middleware/trust configuration the
Dockerfile now applies in front of the real app and confirms the rate
limiter's key then differentiates by `X-Forwarded-For` instead of collapsing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from tests.conftest import TEST_PASSWORD
from tests.conftest import authed_session as _authed_session

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.unit
def test_login_rate_limit_key_differentiates_by_forwarded_for_once_trusted(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path, time_zone="UTC")
    trusted_client = TestClient(
        ProxyHeadersMiddleware(s.client.app, trusted_hosts="*")  # type: ignore[arg-type]
    )

    def attempt(forwarded_for: str, password: str) -> int:
        return trusted_client.post(
            "/api/auth/login",
            json={"email": "person@example.com", "password": password},
            headers={"X-Forwarded-For": forwarded_for},
        ).status_code

    for _ in range(5):
        assert attempt("198.51.100.1", "wrong password") == 401
    assert attempt("198.51.100.1", "wrong password") == 429

    # A different forwarded-for address has its own bucket: the victim's own
    # correct password from "elsewhere" is never blocked by the attacker's
    # failures, which is exactly what the shared-origin collapse broke.
    response = trusted_client.post(
        "/api/auth/login",
        json={"email": "person@example.com", "password": TEST_PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert response.status_code == 200


@pytest.mark.unit
def test_backend_image_trusts_forwarded_headers_from_its_only_possible_peer() -> None:
    """Guards the Dockerfile flag the test above relies on staying in place."""
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text()
    assert "--forwarded-allow-ips=*" in dockerfile
