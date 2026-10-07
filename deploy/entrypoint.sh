#!/usr/bin/env bash
# PID 1 is tini; this script starts uvicorn and Next, waits until both answer, then starts nginx
# on $PORT. If any of the three exits, the others are stopped and the container exits non-zero
# so Cloud Run replaces the instance. SIGTERM (Cloud Run shutdown) is forwarded to all three.
set -euo pipefail

PORT="${PORT:-8080}"
PID_DIR=/tmp/pids
mkdir -p "$PID_DIR" /tmp/nginx
sed "s/__PORT__/${PORT}/" /app/deploy/nginx.conf.template >/tmp/nginx/nginx.conf

uvicorn pomodoro.entrypoints.app:app --host 127.0.0.1 --port 8000 &
echo $! >"$PID_DIR/uvicorn.pid"

(cd /app/frontend && PORT=3000 HOSTNAME=127.0.0.1 BACKEND_ORIGIN=http://127.0.0.1:8000 exec node server.js) &
echo $! >"$PID_DIR/next.pid"

stop_all() {
  # shellcheck disable=SC2046
  kill -TERM $(jobs -p) 2>/dev/null || true
}
trap stop_all TERM INT

wait_for() {
  local url=$1
  for _ in $(seq 1 120); do
    if python -c "import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1)" "$url" 2>/dev/null; then
      return 0
    fi
    # Bail out early if a process already died instead of waiting the full timeout.
    for name in uvicorn next; do
      kill -0 "$(cat "$PID_DIR/$name.pid")" 2>/dev/null || { echo "entrypoint: $name exited during startup" >&2; stop_all; exit 1; }
    done
    sleep 0.5
  done
  echo "entrypoint: $url not ready after 60s" >&2
  stop_all
  exit 1
}
wait_for http://127.0.0.1:8000/health
wait_for http://127.0.0.1:3000/login

nginx -c /tmp/nginx/nginx.conf -e /dev/stderr -g 'daemon off;' &
echo $! >"$PID_DIR/nginx.pid"

set +e
wait -n
status=$?
stop_all
wait
# A server exiting on its own (even with 0) is a failure; a signal keeps its 128+N status.
if [ "$status" -eq 0 ]; then
  status=1
fi
exit "$status"
