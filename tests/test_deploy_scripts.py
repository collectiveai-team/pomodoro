"""Deploy shell scripts (deploy/scripts/) exercised against local stand-ins."""

from __future__ import annotations

import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "deploy" / "scripts"


def _run(
    script: str, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPTS / script), *args],
        cwd=REPO_ROOT,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def _server(status_for_path: dict[str, int]) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status_for_path.get(self.path, 404))
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()


@pytest.fixture
def healthy_app() -> Iterator[str]:
    yield from _server({"/api/health": 200, "/login": 200})


@pytest.fixture
def broken_frontend() -> Iterator[str]:
    yield from _server({"/api/health": 200, "/login": 502})


FAST = {"SMOKE_ATTEMPTS": "2", "SMOKE_DELAY_SECONDS": "0"}


@pytest.mark.unit
def test_smoke_passes_when_health_and_login_answer_200(healthy_app: str) -> None:
    result = _run("smoke.sh", healthy_app, env=FAST)
    assert result.returncode == 0, result.stderr


@pytest.mark.unit
def test_smoke_fails_when_login_is_not_200(broken_frontend: str) -> None:
    result = _run("smoke.sh", broken_frontend, env=FAST)
    assert result.returncode != 0
    assert "/login -> 502" in result.stderr


@pytest.mark.unit
def test_smoke_fails_when_nothing_listens() -> None:
    result = _run("smoke.sh", "http://127.0.0.1:9", env=FAST)
    assert result.returncode != 0
