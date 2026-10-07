#!/usr/bin/env bash
# Smoke check a deployed revision: GET /api/health and GET /login must both return 200.
# Usage: smoke.sh <base-url>. Retries cover a cold start (Cloud Run + Neon waking up).
set -euo pipefail

base="${1:?usage: smoke.sh <base-url>}"
attempts="${SMOKE_ATTEMPTS:-5}"
delay="${SMOKE_DELAY_SECONDS:-5}"

for path in /api/health /login; do
  code=000
  for _ in $(seq 1 "$attempts"); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${base}${path}" || true)
    [ "$code" = 200 ] && break
    sleep "$delay"
  done
  if [ "$code" != 200 ]; then
    echo "smoke: ${path} -> ${code}" >&2
    exit 1
  fi
  echo "smoke: ${path} -> 200"
done
