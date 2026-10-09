"""Unit tests for the FastAPI app factory: health round-trip and the domain-error handler."""

from __future__ import annotations

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from pomodoro.core.errors import DomainError
from pomodoro.entrypoints.app import create_app

pytestmark = pytest.mark.unit


def test_health_round_trips_through_the_test_client() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_domain_error_maps_to_the_single_error_response_shape() -> None:
    app = create_app()
    throwaway = APIRouter()

    @throwaway.get("/api/v1/_throwaway")
    def _raise_domain_error() -> None:
        raise DomainError("boom")

    app.include_router(throwaway)
    client = TestClient(app)

    response = client.get("/api/v1/_throwaway")

    assert response.status_code == 400
    assert response.json() == {"detail": "boom"}
