"""Dump the FastAPI app's OpenAPI schema to stdout as JSON.

Used by the frontend to generate its TypeScript client (openapi-typescript + openapi-fetch) and
by CI to check that the committed generated client has not drifted (User Story 91). Run with
`uv run python backend/scripts/export_openapi.py`.
"""

from __future__ import annotations

import json

from pomodoro.entrypoints.app import app

if __name__ == "__main__":
    print(json.dumps(app.openapi()))
