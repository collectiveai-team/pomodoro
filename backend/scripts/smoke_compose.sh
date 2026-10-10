#!/usr/bin/env bash
# Compose lifecycle shared by the health smoke and the Playwright E2E job: build, migrate
# explicitly (never at app startup, ADR-0002), start, wait for /api/health through the
# frontend's same-origin rewrite, optionally run a command against it, always tear down.
# Set FRONTEND_PORT if 3000 is taken. Usage: smoke_compose.sh [command [args...]]
# The command runs with BASE_URL set to the frontend's origin.
set -euo pipefail

cd "$(dirname "$0")/../.."

export FRONTEND_PORT="${FRONTEND_PORT:-3000}"
export BASE_URL="http://localhost:${FRONTEND_PORT}"

teardown() {
  docker compose down -v
}
trap teardown EXIT

docker compose build
docker compose run --rm migrate
docker compose up -d --wait

healthy=0
for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/api/health"; then
    healthy=1
    echo
    break
  fi
  sleep 2
done

if [ "$healthy" -ne 1 ]; then
  echo "smoke: /api/health did not respond" >&2
  docker compose logs --tail=50 >&2
  exit 1
fi

echo "smoke: ok"
if [ "$#" -gt 0 ]; then
  "$@"
fi
