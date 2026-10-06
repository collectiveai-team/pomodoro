"""Smoke test: the FastAPI app boots and the health route responds."""

import pytest
from fastapi.testclient import TestClient
from pomodoro.entrypoints.app import create_app


@pytest.mark.unit
def test_health_route_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
