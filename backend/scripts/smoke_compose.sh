#!/usr/bin/env bash
# Smoke check for the docker compose stack: build, migrate explicitly, start, hit /api/health
# through the frontend's same-origin rewrite. Set FRONTEND_PORT if 3000 is taken.
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose build
docker compose run --rm migrate
docker compose up -d --wait

for _ in $(seq 1 30); do
  if curl -fsS http://localhost:${FRONTEND_PORT:-3000}/api/health; then
    echo
    echo "smoke: ok"
    docker compose down -v
    exit 0
  fi
  sleep 2
done

echo "smoke: /api/health did not respond" >&2
docker compose logs --tail=50 >&2
docker compose down -v
exit 1
