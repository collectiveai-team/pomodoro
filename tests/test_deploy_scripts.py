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
    from collections.abc import Iterator, Mapping

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


FAKE_GCLOUD = """#!/usr/bin/env bash
# Records every call; FAIL_ON makes the matching call fail.
echo "$*" >> "$GCLOUD_LOG"
case "$*" in
  *"$FAIL_ON"*) [ -n "$FAIL_ON" ] && exit 1 ;;
esac
case "$*" in
  "run services describe"*"status.traffic"*) echo "$CANDIDATE_URL" ;;
  "run services describe"*"status.url"*) echo "https://service.example" ;;
esac
exit 0
"""


@pytest.fixture
def fake_gcloud(tmp_path: Path) -> Mapping[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gcloud = bin_dir / "gcloud"
    gcloud.write_text(FAKE_GCLOUD)
    gcloud.chmod(0o755)
    env = dict(FAST)
    env.update(
        PATH=f"{bin_dir}:{os.environ['PATH']}",
        GCLOUD_LOG=str(tmp_path / "gcloud.log"),
        GCP_REGION="southamerica-east1",
        SERVICE_NAME="pomodoro-qa",
        MIGRATE_JOB_NAME="pomodoro-qa-migrate",
        FAIL_ON="",
    )
    return env


def _calls(env: Mapping[str, str]) -> list[str]:
    log = Path(env["GCLOUD_LOG"])
    return log.read_text().splitlines() if log.exists() else []


IMAGE = "southamerica-east1-docker.pkg.dev/p/pomodoro/pomodoro-app:abc123"


@pytest.mark.unit
def test_deploy_migrates_then_deploys_without_traffic_then_promotes(
    fake_gcloud: Mapping[str, str], healthy_app: str
) -> None:
    result = _run("deploy-env.sh", IMAGE, env={**fake_gcloud, "CANDIDATE_URL": healthy_app})
    assert result.returncode == 0, result.stderr
    calls = _calls(fake_gcloud)
    order = [
        next(i for i, c in enumerate(calls) if c.startswith("run jobs update pomodoro-qa-migrate")),
        next(
            i for i, c in enumerate(calls) if c.startswith("run jobs execute pomodoro-qa-migrate")
        ),
        next(
            i
            for i, c in enumerate(calls)
            if c.startswith("run deploy pomodoro-qa") and "--no-traffic" in c
        ),
        next(
            i
            for i, c in enumerate(calls)
            if c.startswith("run services update-traffic pomodoro-qa") and "--to-latest" in c
        ),
    ]
    assert order == sorted(order)
    assert "--wait" in calls[order[1]]


@pytest.mark.unit
def test_failed_migration_never_deploys(fake_gcloud: Mapping[str, str], healthy_app: str) -> None:
    env = {**fake_gcloud, "CANDIDATE_URL": healthy_app, "FAIL_ON": "run jobs execute"}
    result = _run("deploy-env.sh", IMAGE, env=env)
    assert result.returncode != 0
    assert not any(c.startswith("run deploy") for c in _calls(fake_gcloud))


@pytest.mark.unit
def test_failed_smoke_keeps_traffic_on_previous_revision(
    fake_gcloud: Mapping[str, str], broken_frontend: str
) -> None:
    result = _run("deploy-env.sh", IMAGE, env={**fake_gcloud, "CANDIDATE_URL": broken_frontend})
    assert result.returncode != 0
    assert not any("update-traffic" in c for c in _calls(fake_gcloud))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo_with_main_and_side(tmp_path: Path) -> tuple[Path, str, str]:
    """Return a clone whose origin/main has one commit, plus a side commit not on main."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(
        origin,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "on main",
    )
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    on_main = _git(clone, "rev-parse", "HEAD")
    _git(clone, "checkout", "-q", "-b", "side")
    _git(
        clone,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "side",
    )
    return clone, on_main, _git(clone, "rev-parse", "HEAD")


def _verify(repo: Path, sha: str, env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPTS / "verify-release.sh"), sha, f"{IMAGE[:-6]}{sha}"],
        cwd=repo,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.unit
def test_verify_release_accepts_a_main_commit_with_an_image(
    repo_with_main_and_side: tuple[Path, str, str], fake_gcloud: Mapping[str, str]
) -> None:
    repo, on_main, _ = repo_with_main_and_side
    assert _verify(repo, on_main, fake_gcloud).returncode == 0


@pytest.mark.unit
def test_verify_release_rejects_a_commit_not_on_main(
    repo_with_main_and_side: tuple[Path, str, str], fake_gcloud: Mapping[str, str]
) -> None:
    repo, _, side = repo_with_main_and_side
    result = _verify(repo, side, fake_gcloud)
    assert result.returncode != 0
    assert "not on main" in result.stderr


@pytest.mark.unit
def test_verify_release_rejects_a_missing_image(
    repo_with_main_and_side: tuple[Path, str, str], fake_gcloud: Mapping[str, str]
) -> None:
    repo, on_main, _ = repo_with_main_and_side
    result = _verify(repo, on_main, {**fake_gcloud, "FAIL_ON": "artifacts docker images describe"})
    assert result.returncode != 0
    assert "no image" in result.stderr
