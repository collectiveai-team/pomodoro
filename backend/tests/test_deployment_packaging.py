"""Guards for the deployment packaging contract (T25, ADR-0002).

Migrations are an explicit deploy step, never a side effect of starting the app.
"""

import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.unit
def test_compose_runs_migrations_as_a_separate_step_the_backend_waits_for():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert services["migrate"]["command"] == ["alembic", "upgrade", "head"]
    assert (
        services["backend"]["depends_on"]["migrate"]["condition"]
        == "service_completed_successfully"
    )
    assert "alembic" not in str(services["backend"].get("command", ""))


@pytest.mark.unit
def test_backend_image_starts_uvicorn_without_migrating():
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text()
    cmd_lines = [line for line in dockerfile.splitlines() if line.startswith("CMD")]

    assert len(cmd_lines) == 1
    assert "uvicorn" in cmd_lines[0]
    assert "alembic" not in cmd_lines[0]


@pytest.mark.unit
def test_hadolint_hook_covers_nested_dockerfiles():
    prek = tomllib.loads((REPO_ROOT / "prek.toml").read_text())
    hooks = [h for repo in prek["repos"] for h in repo["hooks"] if h["id"] == "hadolint-docker"]

    assert hooks
    pattern = re.compile(hooks[0]["files"])
    assert pattern.search("Dockerfile")
    assert pattern.search("backend/Dockerfile")
    assert pattern.search("frontend/Dockerfile")
