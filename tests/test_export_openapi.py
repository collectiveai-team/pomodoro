"""Proves the OpenAPI export script writes the real app schema to a given path.

The frontend's generated API client (T19) is built from this file's output, so a
regression here would silently break `pnpm run generate:api-client` in CI.
"""

import json
from typing import TYPE_CHECKING

import pytest
from pomodoro.entrypoints import export_openapi

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def test_main_writes_openapi_schema_to_the_given_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_path = tmp_path / "nested" / "openapi.json"
    monkeypatch.setattr("sys.argv", ["pomodoro-export-openapi", str(output_path)])

    export_openapi.main()

    schema = json.loads(output_path.read_text())
    assert schema["info"]["title"] == "Pomodoro Collective API"
    assert "/api/tasks" in schema["paths"]


def test_main_defaults_to_dot_tmp_openapi_json_under_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["pomodoro-export-openapi"])
    monkeypatch.chdir(tmp_path)

    export_openapi.main()

    schema = json.loads((tmp_path / ".tmp" / "openapi.json").read_text())
    assert schema["info"]["title"] == "Pomodoro Collective API"
