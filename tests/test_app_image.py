"""Behavior of the single Cloud Run image (deploy/Dockerfile).

Skipped unless the image is running: APP_IMAGE_BASE_URL points at docker-compose.app.yml's app
service, APP_IMAGE names the built image for the tests that start their own container.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("APP_IMAGE_BASE_URL")
IMAGE = os.environ.get("APP_IMAGE")

needs_running_app = pytest.mark.skipif(BASE_URL is None, reason="APP_IMAGE_BASE_URL not set")
needs_image = pytest.mark.skipif(IMAGE is None, reason="APP_IMAGE not set")


@pytest.mark.e2e
@needs_running_app
def test_frontend_ready_as_soon_as_container_is_healthy() -> None:
    response = httpx.get(f"{BASE_URL}/login", timeout=10)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.e2e
@needs_running_app
def test_api_health_reaches_backend_through_nginx() -> None:
    response = httpx.get(f"{BASE_URL}/api/health", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)


def _start_standalone_container() -> str:
    """Start the image without Postgres: SQLite is enough to boot and serve /health."""
    name = f"pomodoro-app-test-{uuid.uuid4().hex[:8]}"
    started = _docker(
        "run", "-d", "--name", name, "-e", "DATABASE_URL=sqlite:////tmp/app.db", IMAGE or ""
    )
    assert started.returncode == 0, started.stderr
    probe = (
        "import urllib.request; "
        "urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=1)"
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if _docker("exec", name, "python", "-c", probe).returncode == 0:
            return name
        time.sleep(1)
    logs = _docker("logs", name)
    _docker("rm", "-f", name)
    pytest.fail(f"container never became ready:\n{logs.stdout}\n{logs.stderr}")


def _exit_code_after(name: str, timeout_s: int = 30) -> int:
    waited = subprocess.run(
        ["docker", "wait", name], capture_output=True, text=True, timeout=timeout_s, check=True
    )
    return int(waited.stdout.strip())


@pytest.mark.e2e
@needs_image
@pytest.mark.parametrize("process", ["uvicorn", "next", "nginx"])
def test_container_exits_non_zero_when_a_process_dies(process: str) -> None:
    name = _start_standalone_container()
    try:
        killed = _docker("exec", name, "sh", "-c", f"kill -TERM $(cat /tmp/pids/{process}.pid)")
        assert killed.returncode == 0, killed.stderr
        assert _exit_code_after(name) != 0
    finally:
        _docker("rm", "-f", name)


@pytest.mark.e2e
@needs_image
def test_sigterm_shuts_down_cleanly_before_the_kill_timeout() -> None:
    name = _start_standalone_container()
    try:
        _docker("stop", "--time", "10", name)
        # 137 would mean docker had to SIGKILL us after the grace period.
        assert _exit_code_after(name) != 137
    finally:
        _docker("rm", "-f", name)
