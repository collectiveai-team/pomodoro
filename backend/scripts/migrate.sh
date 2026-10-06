#!/usr/bin/env sh
# Applies pending Alembic migrations against $DATABASE_URL (SQLite or
# PostgreSQL). Run as its own explicit deploy step -- never automatically on
# container start (Despliegue section, issue #12):
#
#   docker run --rm -e DATABASE_URL=... pomodoro-backend backend/scripts/migrate.sh
#
# Outside the image, run from the repo root with `uv run backend/scripts/migrate.sh`.
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repo_root"

exec alembic upgrade head
