"""Unit tests for the app factory: health endpoint, OpenAPI, and the error envelope."""

import pytest
from fastapi.testclient import TestClient
from pomodoro.entrypoints.app import create_app

pytestmark = pytest.mark.unit


def test_health_endpoint_returns_ok_with_server_time() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "server_time" in body


def test_openapi_json_is_served() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Pomodoro Collective"


def test_unknown_route_returns_the_error_envelope() -> None:
    client = TestClient(create_app())

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert set(body.keys()) == {"detail", "code"}
    assert body["code"] == "http_error"


def test_request_validation_errors_return_the_error_envelope() -> None:
    app = create_app()

    @app.get("/test-only/validate")
    def _validate(count: int) -> int:
        return count

    client = TestClient(app)

    response = client.get("/test-only/validate", params={"count": "not-an-int"})

    assert response.status_code == 422
    body = response.json()
    assert set(body.keys()) == {"detail", "code"}
    assert body["code"] == "validation_error"
