"""Exports the FastAPI app's OpenAPI schema to a JSON file.

The frontend's generated API client (T19) is built from this file via
openapi-typescript, so this is the one supported source of truth for that
generation step instead of requiring a running server.
"""

import json
import sys
from pathlib import Path

from pomodoro.entrypoints.app import app

DEFAULT_OUTPUT_PATH = Path(".tmp/openapi.json")


def main() -> None:
    """Write the app's OpenAPI schema to argv[1], or `.tmp/openapi.json` by default."""
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n")


if __name__ == "__main__":
    main()
