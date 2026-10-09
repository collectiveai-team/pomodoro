# Cloud Run Deploy (QA y prod) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Desplegar Pomodoro Collective en Cloud Run (`pomodoro-qa` y `pomodoro-prod`, min 0 / max 1) con una imagen única
(nginx + Next.js + uvicorn), base Neon, infraestructura en Terraform y CI/CD con GitHub Actions + WIF.

**Architecture:** Una imagen `deploy/Dockerfile` corre tres procesos bajo `tini` + `entrypoint.sh`. nginx escucha en `$PORT`
y rutea `/api/` a uvicorn (`127.0.0.1:8000`) y el resto a Next (`127.0.0.1:3000`). Terraform (`deploy/terraform/`) declara GCP,
Neon y GitHub; el pipeline solo cambia la imagen. `deploy.yml` construye en cada push a `main`, migra con un Cloud Run Job,
despliega sin tráfico, hace smoke check sobre la revisión candidata y recién ahí mueve el tráfico. Prod promueve la misma
imagen al publicar un Release.

**Tech Stack:** Docker (BuildKit), nginx (Debian bookworm), tini, bash, Terraform ≥ 1.9 (providers `hashicorp/google`,
`kislerdm/neon`, `integrations/github`), GitHub Actions (`google-github-actions/auth`, `setup-gcloud`), pytest + httpx.

**Spec:** `docs/superpowers/specs/2026-10-07-cloud-run-deploy-design.md`

## Global Constraints

- Región GCP `southamerica-east1`; región Neon `aws-sa-east-1`.
- Servicios `pomodoro-qa` y `pomodoro-prod`; jobs `pomodoro-qa-migrate` y `pomodoro-prod-migrate`.
- Escalado `min_instance_count = 0`, `max_instance_count = 1`; 1 vCPU / 1 GiB por defecto (variables de Terraform).
- Secretos `pomodoro-qa-database-url` y `pomodoro-prod-database-url`; SAs `pomodoro-qa-run`, `pomodoro-prod-run`, `pomodoro-deployer`.
- Imagen `<region>-docker.pkg.dev/<project>/pomodoro/pomodoro-app:<sha>`; imagen inicial `pomodoro-app:bootstrap`.
- uvicorn y Next escuchan solo en `127.0.0.1`; uvicorn **sin** `--forwarded-allow-ips` (confía solo en `127.0.0.1`, el default).
- Las migraciones nunca corren al arrancar el contenedor; solo vía `backend/scripts/migrate.sh` (job).
- La imagen corre como usuario no root.
- Acciones de GitHub fijadas por tag (`zizmor.yml` usa `ref-pin`); `permissions: {}` a nivel workflow y mínimos por job;
  `id-token: write` solo en jobs que se autentican; nunca interpolar `${{ }}` dentro de `run:` (pasar por `env:`).
- `checkout` siempre con `persist-credentials: false`.
- `NEON_API_KEY`, `GITHUB_TOKEN` y cualquier `DATABASE_URL` nunca se commitean ni se imprimen; outputs de Terraform con
  secretos van `sensitive = true`.
- Commits convencionales, sin trailers de coautoría de IA, nunca `--no-verify`. Los hooks de prek deben pasar.
- jscpd tiene umbral 1% sobre todo el repo: no duplicar bloques entre workflows/compose; si este plan o el spec provocan
  clones contra los archivos reales, agregar `docs/superpowers/**` al `--ignore` del hook jscpd en `prek.toml`.
- Comandos pesados (builds de imagen) bajo `systemd-run` según `CLAUDE.md`, con log en `.tmp/logs/<cmd>/`.

### Decisiones de implementación que precisan el spec

1. **Health:** el backend expone `GET /health` (sin prefijo). nginx mapea `location = /api/health` → `http://127.0.0.1:8000/health`.
   No se agrega una ruta nueva al backend.
2. **Arranque:** `entrypoint.sh` arranca uvicorn y Next, espera a que ambos respondan y recién entonces arranca nginx. Así el
   startup probe de Cloud Run (`/api/health` vía nginx) solo pasa cuando los tres están listos.
3. **Deploy sin rollback de tráfico:** en vez de desplegar y revertir, `gcloud run deploy --no-traffic --tag candidate`,
   smoke check sobre la URL del tag y `update-traffic --to-latest` solo si pasa. Mismo resultado que el spec (si el smoke
   falla, el tráfico sigue en la revisión anterior) sin dejar el tráfico fijado a una revisión con nombre.
4. **Neon QA:** el provider no permite rotar el password de un rol heredado, y la branch `qa` hereda el rol `pomodoro` de
   prod **con el mismo password**. Para no compartir credenciales, QA usa su propio rol `pomodoro_qa` y su propia base
   `pomodoro_qa`, creados en la branch `qa`. El "reset de QA desde prod" del runbook pasa a ser `pg_dump` de prod +
   `pg_restore --no-owner --role=pomodoro_qa`.
5. **Variables de Actions:** `GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER` y `DEPLOYER_SA` son variables **de repositorio**
   (el job `build` no corre en un environment); `SERVICE_NAME` y `MIGRATE_JOB_NAME` son variables **por environment**.
6. **"Con CI en verde":** `deploy.yml` se dispara en `push` a `main`; el verde lo garantiza la protección de branch de
   `main` exigiendo los checks. El runbook lo deja como prerequisito.
7. **Prod solo desde main:** `deploy-prod` verifica que el commit del release sea ancestro de `origin/main` y que la imagen
   exista antes de tocar nada.

## Review Focus

1. **`X-Forwarded-For` falsificado en Cloud Run.** Con nginx agregando `$remote_addr`, uvicorn toma la última IP no
   confiable, que es el peer de nginx (el frente de Google), no lo que mande el cliente. Un atacante que rota el header
   igual debe recibir 429 al sexto intento. Cubierto por `test_forged_rotating_forwarded_for_still_hits_429` (Task 2) y por
   la verificación manual en QA del runbook (Task 8), que además registra qué IP ve el backend.
2. **Release creado sobre un commit que no está en `main` o sin imagen construida.** `deploy-prod` debe fallar antes de
   migrar. Cubierto por `test_verify_release_rejects_*` (Task 7).
3. **Migración que falla.** El servicio no debe cambiar de revisión. Cubierto por
   `test_failed_migration_never_deploys` (Task 7) y, en local, por `depends_on: service_completed_successfully` (Task 1).
4. **Smoke check que falla.** El tráfico no debe moverse a la revisión nueva. Cubierto por
   `test_failed_smoke_keeps_traffic_on_previous_revision` (Task 7).
5. **Arranque en frío.** El primer request a `/` justo después de que el contenedor está "healthy" no debe dar 502 porque
   Next todavía no arrancó. Cubierto por `test_frontend_ready_as_soon_as_container_is_healthy` (Task 1) y por el startup
   probe con margen de 60 s (Task 5).

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `deploy/Dockerfile` | Imagen única multi-stage (venv backend, build Next standalone, runtime Python + Node + nginx + tini) |
| `deploy/Dockerfile.dockerignore` | Contexto de build para la imagen única (el `.dockerignore` raíz excluye `frontend/`) |
| `deploy/nginx.conf.template` | Ruteo `/api/health`, `/api/`, `/` sobre `__PORT__` |
| `deploy/entrypoint.sh` | Arranque ordenado, espera de readiness, supervisión `wait -n`, propagación de `SIGTERM` |
| `docker-compose.app.yml` | Imagen única + Postgres local + migración |
| `deploy/scripts/smoke.sh` | Smoke check `/api/health` y `/login` con reintentos |
| `deploy/scripts/deploy-env.sh` | Migrar → desplegar sin tráfico → smoke → mover tráfico |
| `deploy/scripts/verify-release.sh` | Commit en `main` + imagen existente |
| `.github/actions/deploy-env/action.yml` | Auth WIF + gcloud + `deploy-env.sh` (compartido por QA y prod) |
| `.github/workflows/deploy.yml` | build, deploy-qa, deploy-prod |
| `.github/workflows/deploy-ci.yml` | PRs: `app-image` y `terraform` |
| `deploy/terraform/*.tf`, `modules/environment/*.tf` | Infraestructura |
| `tests/test_deploy_config.py` | Guardas estáticas (unit) sobre la config de deploy |
| `tests/test_app_image.py` | Tests de la imagen única corriendo (marker `e2e`, se saltean sin la imagen) |
| `tests/test_deploy_scripts.py` | Tests de los scripts con un `gcloud` falso (unit) |
| `README.md`, `docs/deploy.md`, `docs/adr/0004-single-container-nginx-cloud-run.md` | Documentación |

---

### Task 1: Imagen única con nginx, readiness y supervisión

**Files:**
- Create: `deploy/Dockerfile`, `deploy/Dockerfile.dockerignore`, `deploy/nginx.conf.template`, `deploy/entrypoint.sh`
- Create: `docker-compose.app.yml`
- Create: `tests/test_deploy_config.py`, `tests/test_app_image.py`

**Interfaces:**
- Produces: imagen local `pomodoro-app:local`; `ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/entrypoint.sh"]`;
  migración con `command: ["/app/backend/scripts/migrate.sh"]`; PIDs en `/tmp/pids/{uvicorn,next,nginx}.pid`;
  servicio compose `app` publicado en `${APP_PORT:-8080}`; variables de test `APP_IMAGE_BASE_URL` (URL de la app) y
  `APP_IMAGE` (tag de la imagen).

- [ ] **Step 1: Escribir las guardas estáticas (fallan porque no existen los archivos)**

`tests/test_deploy_config.py`:

```python
"""Static guards for the Cloud Run deploy configuration (deploy/, deploy.yml, Terraform).

They read tracked files only, so they run in the default unit suite.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"


@pytest.mark.unit
def test_entrypoint_binds_internal_processes_to_loopback_only() -> None:
    entrypoint = (DEPLOY_DIR / "entrypoint.sh").read_text()
    assert "--host 127.0.0.1 --port 8000" in entrypoint
    assert "HOSTNAME=127.0.0.1" in entrypoint


@pytest.mark.unit
def test_entrypoint_keeps_uvicorn_default_proxy_trust() -> None:
    """Trust stays at 127.0.0.1 (nginx); a blanket trust would reopen the rate-limit bypass."""
    entrypoint = (DEPLOY_DIR / "entrypoint.sh").read_text()
    assert "--forwarded-allow-ips" not in entrypoint
    assert "FORWARDED_ALLOW_IPS" not in entrypoint


@pytest.mark.unit
def test_nginx_maps_api_health_to_backend_health_route() -> None:
    nginx = (DEPLOY_DIR / "nginx.conf.template").read_text()
    assert re.search(r"location = /api/health \{\s*proxy_pass http://127\.0\.0\.1:8000/health;", nginx)
    assert "location /api/ {" in nginx
    assert "listen __PORT__;" in nginx


@pytest.mark.unit
def test_app_image_never_migrates_on_start() -> None:
    entrypoint = (DEPLOY_DIR / "entrypoint.sh").read_text()
    assert "alembic" not in entrypoint
    assert "migrate.sh" not in entrypoint


@pytest.mark.unit
def test_app_image_runs_as_non_root() -> None:
    dockerfile = (DEPLOY_DIR / "Dockerfile").read_text()
    user_lines = [line for line in dockerfile.splitlines() if line.startswith("USER ")]
    assert user_lines, "deploy/Dockerfile must drop root"
    assert user_lines[-1].split()[1].split(":")[0] not in {"0", "root"}
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_deploy_config.py -q`
Expected: 5 FAIL con `FileNotFoundError` sobre `deploy/...`.

- [ ] **Step 3: Escribir `deploy/nginx.conf.template`**

```nginx
# Rendered by deploy/entrypoint.sh: __PORT__ -> $PORT (Cloud Run injects 8080).
# Runs as the image's non-root user, so every writable path lives under /tmp.
worker_processes 1;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;

events {
  worker_connections 512;
}

http {
  access_log /dev/stdout;
  server_tokens off;
  client_max_body_size 1m;
  client_body_temp_path /tmp/nginx/client_body;
  proxy_temp_path /tmp/nginx/proxy;
  fastcgi_temp_path /tmp/nginx/fastcgi;
  uwsgi_temp_path /tmp/nginx/uwsgi;
  scgi_temp_path /tmp/nginx/scgi;

  # Cloud Run terminates TLS and sets X-Forwarded-Proto; keep it, or fall back to our own scheme locally.
  map $http_x_forwarded_proto $forwarded_proto {
    default $http_x_forwarded_proto;
    "" $scheme;
  }

  proxy_http_version 1.1;
  proxy_set_header Connection "";
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto $forwarded_proto;
  # uvicorn trusts only 127.0.0.1 (us) and takes the right-most untrusted hop: the peer nginx saw,
  # never an address the client wrote into the header.
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

  server {
    listen __PORT__;

    # The backend's health route has no /api prefix (api/health.py).
    location = /api/health {
      proxy_pass http://127.0.0.1:8000/health;
    }

    location /api/ {
      proxy_pass http://127.0.0.1:8000;
    }

    location / {
      proxy_pass http://127.0.0.1:3000;
    }
  }
}
```

- [ ] **Step 4: Escribir `deploy/entrypoint.sh` (y `chmod +x`)**

```bash
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
```

- [ ] **Step 5: Escribir `deploy/Dockerfile` y `deploy/Dockerfile.dockerignore`**

`deploy/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1
#
# Single Cloud Run image: nginx on $PORT in front of uvicorn (127.0.0.1:8000) and the Next.js
# standalone server (127.0.0.1:3000). See docs/adr/0004-single-container-nginx-cloud-run.md.
# Build context is the repo root; deploy/Dockerfile.dockerignore scopes it.
#
#   docker build -f deploy/Dockerfile -t pomodoro-app:local .
#
# Migrations never run on start: the Cloud Run Job overrides the command with
# /app/backend/scripts/migrate.sh.

ARG PYTHON_VERSION=3.14-slim-bookworm
ARG NODE_VERSION=24-slim

FROM ghcr.io/astral-sh/uv:0.11.12 AS uv
FROM node:${NODE_VERSION} AS node

# ---- backend: same resolution as backend/Dockerfile (see its comments) ----
FROM python:${PYTHON_VERSION} AS backend-builder
COPY --from=uv /uv /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
COPY alembic.ini ./
COPY backend ./backend

# ---- frontend: same standalone build as frontend/Dockerfile ----
FROM node:${NODE_VERSION} AS frontend-builder
RUN corepack enable
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

# ---- runtime: Python base + Node binary + nginx + tini ----
FROM python:${PYTHON_VERSION} AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 pomodoro \
    && useradd --system --uid 1000 --gid pomodoro --home-dir /app pomodoro
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY --from=backend-builder --chown=pomodoro:pomodoro /app /app
COPY --from=frontend-builder --chown=pomodoro:pomodoro /app/public /app/frontend/public
COPY --from=frontend-builder --chown=pomodoro:pomodoro /app/.next/standalone /app/frontend
COPY --from=frontend-builder --chown=pomodoro:pomodoro /app/.next/static /app/frontend/.next/static
COPY --chown=pomodoro:pomodoro deploy/nginx.conf.template deploy/entrypoint.sh /app/deploy/
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/backend" \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    PORT=8080

USER 1000:1000
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/entrypoint.sh"]
```

`deploy/Dockerfile.dockerignore` (BuildKit lo usa en lugar del `.dockerignore` raíz para este Dockerfile):

```
# Context for deploy/Dockerfile: only what it copies.
**
!pyproject.toml
!uv.lock
!alembic.ini
!backend/
!frontend/
!deploy/nginx.conf.template
!deploy/entrypoint.sh
**/__pycache__/
**/*.py[cod]
frontend/node_modules/
frontend/.next/
```

- [ ] **Step 6: Escribir `docker-compose.app.yml`**

```yaml
# The single Cloud Run image (deploy/Dockerfile) against a local Postgres, to test it exactly as
# it runs in Cloud Run. Separate project name so it never shares volumes with docker-compose.yml.
#
#   docker compose -f docker-compose.app.yml up -d --build --wait
name: pomodoro-app

x-app-image: &app-image
  build:
    context: .
    dockerfile: deploy/Dockerfile
  image: pomodoro-app:local
  environment:
    DATABASE_URL: postgresql+psycopg://pomodoro:pomodoro@db:5432/pomodoro

services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: pomodoro
      POSTGRES_PASSWORD: pomodoro
      POSTGRES_DB: pomodoro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pomodoro -d pomodoro"]
      interval: 2s
      timeout: 3s
      retries: 30

  migrate:
    <<: *app-image
    entrypoint: ["/app/backend/scripts/migrate.sh"]
    depends_on:
      db:
        condition: service_healthy

  app:
    <<: *app-image
    ports:
      - "${APP_PORT:-8080}:8080"
    depends_on:
      migrate:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2)"]
      interval: 3s
      timeout: 3s
      retries: 40
```

- [ ] **Step 7: Correr las guardas estáticas**

Run: `uv run pytest tests/test_deploy_config.py -q`
Expected: 5 PASS.

- [ ] **Step 8: Escribir los tests de la imagen corriendo**

`tests/test_app_image.py`:

```python
"""Behavior of the single Cloud Run image (deploy/Dockerfile).

Skipped unless the image is running: APP_IMAGE_BASE_URL points at docker-compose.app.yml's app
service, APP_IMAGE names the built image for the tests that start their own container.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("APP_IMAGE_BASE_URL")
IMAGE = os.environ.get("APP_IMAGE")

needs_running_app = pytest.mark.skipif(BASE_URL is None, reason="APP_IMAGE_BASE_URL not set")
needs_image = pytest.mark.skipif(IMAGE is None, reason="APP_IMAGE not set")


@pytest.mark.e2e
@needs_running_app
def test_frontend_ready_as_soon_as_container_is_healthy() -> None:
    response = httpx.get(f"{BASE_URL}/login", timeout=10)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.e2e
@needs_running_app
def test_api_health_reaches_backend_through_nginx() -> None:
    response = httpx.get(f"{BASE_URL}/api/health", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)


def _start_standalone_container() -> str:
    """Start the image without Postgres: SQLite is enough to boot and serve /health."""
    name = f"pomodoro-app-test-{uuid.uuid4().hex[:8]}"
    started = _docker("run", "-d", "--name", name, "-e", "DATABASE_URL=sqlite:////tmp/app.db", IMAGE or "")
    assert started.returncode == 0, started.stderr
    probe = "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=1)"
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if _docker("exec", name, "python", "-c", probe).returncode == 0:
            return name
        time.sleep(1)
    logs = _docker("logs", name)
    _docker("rm", "-f", name)
    pytest.fail(f"container never became ready:\n{logs.stdout}\n{logs.stderr}")


def _exit_code_after(name: str, timeout_s: int = 30) -> int:
    waited = subprocess.run(["docker", "wait", name], capture_output=True, text=True, timeout=timeout_s, check=True)
    return int(waited.stdout.strip())


@pytest.mark.e2e
@needs_image
@pytest.mark.parametrize("process", ["uvicorn", "next", "nginx"])
def test_container_exits_non_zero_when_a_process_dies(process: str) -> None:
    name = _start_standalone_container()
    try:
        killed = _docker("exec", name, "sh", "-c", f"kill -TERM $(cat /tmp/pids/{process}.pid)")
        assert killed.returncode == 0, killed.stderr
        assert _exit_code_after(name) != 0
    finally:
        _docker("rm", "-f", name)


@pytest.mark.e2e
@needs_image
def test_sigterm_shuts_down_cleanly_before_the_kill_timeout() -> None:
    name = _start_standalone_container()
    try:
        _docker("stop", "--time", "10", name)
        # 137 would mean docker had to SIGKILL us after the grace period.
        assert _exit_code_after(name) != 137
    finally:
        _docker("rm", "-f", name)
```

- [ ] **Step 9: Construir la imagen y correr los tests**

```bash
cmd=app-image-build; ts=$(date +%Y-%m-%dT%H-%M-%S); log=.tmp/logs/$cmd/${ts}_wall-stats.log; mkdir -p ".tmp/logs/$cmd"
systemd-run --user --scope -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=400% \
  /usr/bin/time -v -o "$log" docker compose -f docker-compose.app.yml up -d --build --wait --wait-timeout 300
APP_IMAGE_BASE_URL=http://localhost:8080 APP_IMAGE=pomodoro-app:local uv run pytest tests/test_app_image.py -v
```

Expected: 6 PASS (2 de ruteo, 3 parametrizados de muerte de proceso, 1 de SIGTERM). Si un test de muerte falla, revisar
`docker logs` del contenedor y el bloque `wait -n` del entrypoint antes de tocar los tests.

- [ ] **Step 10: Verificar que la suite por defecto los saltea**

Run: `uv run pytest -m "not integration" -q`
Expected: verde; los de `test_app_image.py` aparecen como skipped.

- [ ] **Step 11: Gates y commit**

```bash
prek run --all-files
git add deploy/Dockerfile deploy/Dockerfile.dockerignore deploy/nginx.conf.template deploy/entrypoint.sh \
  docker-compose.app.yml tests/test_deploy_config.py tests/test_app_image.py
git commit -m "feat(deploy): add the single nginx + Next + uvicorn image for Cloud Run"
```

---

### Task 2: Flujo de sesión, rate limit tras nginx, smoke script y CI `app-image`

**Files:**
- Create: `deploy/scripts/smoke.sh`
- Create: `.github/workflows/deploy-ci.yml`
- Modify: `tests/test_app_image.py` (agregar tests)
- Create: `tests/test_deploy_scripts.py`

**Interfaces:**
- Consumes: `docker-compose.app.yml`, `APP_IMAGE_BASE_URL`, `APP_IMAGE` (Task 1).
- Produces: `deploy/scripts/smoke.sh <base-url>`, sale 0 si `/api/health` y `/login` dan 200; reintentos con
  `SMOKE_ATTEMPTS` (default 5) y `SMOKE_DELAY_SECONDS` (default 5). Workflow `deploy-ci` con job `app-image` (el job
  `terraform` se agrega en Task 3).

- [ ] **Step 1: Agregar los tests de sesión y rate limit a `tests/test_app_image.py`**

```python
def _register(email: str, password: str) -> None:
    response = httpx.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "time_zone": "UTC"},
        timeout=10,
    )
    assert response.status_code == 201, response.text


@pytest.mark.e2e
@needs_running_app
def test_register_login_and_me_through_nginx() -> None:
    email = f"image-{uuid.uuid4().hex[:8]}@example.com"
    password = "correct horse battery staple"
    _register(email, password)

    login = httpx.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=10)
    assert login.status_code == 200, login.text
    # The session cookie is Secure; send it explicitly since the test talks plain HTTP to localhost.
    session_cookie = login.headers["set-cookie"].split(";", 1)[0]

    me = httpx.get(f"{BASE_URL}/api/auth/me", headers={"Cookie": session_cookie}, timeout=10)
    assert me.status_code == 200
    assert me.json()["email"] == email


@pytest.mark.e2e
@needs_running_app
def test_forged_rotating_forwarded_for_still_hits_429() -> None:
    email = f"image-{uuid.uuid4().hex[:8]}@example.com"
    _register(email, "correct horse battery staple")

    def attempt(forged: str) -> int:
        return httpx.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": "wrong password"},
            headers={"X-Forwarded-For": forged},
            timeout=10,
        ).status_code

    for i in range(5):
        assert attempt(f"198.51.100.{i}") == 401
    assert attempt("198.51.100.99") == 429
```

Antes de correr, confirmar el nombre del campo en la respuesta de `/api/auth/me` en `backend/pomodoro/api/auth.py` (línea
~254) y ajustar `me.json()["email"]` si difiere.

- [ ] **Step 2: Escribir `tests/test_deploy_scripts.py` con los tests de `smoke.sh` (fallan: no existe)**

```python
"""Deploy shell scripts (deploy/scripts/) exercised against local stand-ins."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "deploy" / "scripts"


def _run(script: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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

        def log_message(self, *_: object) -> None:
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
```

Run: `uv run pytest tests/test_deploy_scripts.py -q`
Expected: 3 FAIL (`smoke.sh` no existe).

- [ ] **Step 3: Escribir `deploy/scripts/smoke.sh` (y `chmod +x`)**

```bash
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
```

Run: `uv run pytest tests/test_deploy_scripts.py -q` → 3 PASS.

- [ ] **Step 4: Correr los tests de la imagen contra el compose levantado**

```bash
docker compose -f docker-compose.app.yml up -d --build --wait --wait-timeout 300
APP_IMAGE_BASE_URL=http://localhost:8080 APP_IMAGE=pomodoro-app:local uv run pytest tests/test_app_image.py -v
deploy/scripts/smoke.sh http://localhost:8080
docker compose -f docker-compose.app.yml down -v
```

Expected: 8 PASS y el smoke imprime dos líneas `-> 200`. Si el test de 429 falla, **no** relajarlo: es el supuesto de
seguridad del spec. Revisar qué `X-Forwarded-For` llega a uvicorn (log de nginx) y aplicar el plan B del spec.

- [ ] **Step 5: Escribir `.github/workflows/deploy-ci.yml`**

```yaml
name: deploy-ci

# PR gates for the Cloud Run deploy (docs/superpowers/specs/2026-10-07-cloud-run-deploy-design.md):
# build the single image, run it against Postgres and exercise it end to end.

on:
  pull_request:
    paths:
      - "backend/**"
      - "frontend/**"
      - "deploy/**"
      - "docker-compose.app.yml"
      - "pyproject.toml"
      - "uv.lock"
      - "tests/test_app_image.py"
      - ".github/workflows/deploy-ci.yml"

concurrency:
  group: deploy-ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

env:
  UV_VERSION: "0.11.12"
  APP_IMAGE_BASE_URL: "http://localhost:8080"
  APP_IMAGE: "pomodoro-app:local"

jobs:
  app-image:
    name: app-image
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false

      - uses: ./.github/actions/setup-backend
        with:
          uv-version: ${{ env.UV_VERSION }}

      - name: Build and start the single image
        run: docker compose -f docker-compose.app.yml up -d --build --wait --wait-timeout 300

      - name: Single-image tests
        run: uv run pytest tests/test_app_image.py -v

      - name: Smoke script against the image
        run: deploy/scripts/smoke.sh "$APP_IMAGE_BASE_URL"

      - name: Logs
        if: failure()
        run: docker compose -f docker-compose.app.yml logs

      - name: Tear down
        if: always()
        run: docker compose -f docker-compose.app.yml down -v
```

- [ ] **Step 6: Auditar el workflow**

Run: `uvx zizmor .github/workflows/deploy-ci.yml` → sin hallazgos. Si `actionlint` está disponible, `actionlint .github/workflows/deploy-ci.yml`.

- [ ] **Step 7: Gates y commit**

```bash
prek run --all-files
git add deploy/scripts/smoke.sh tests/test_app_image.py tests/test_deploy_scripts.py .github/workflows/deploy-ci.yml
git commit -m "test(deploy): exercise the single image end to end in PR CI"
```

---

### Task 3: Terraform raíz y recursos compartidos (APIs, Artifact Registry, WIF, deployer)

**Files:**
- Create: `deploy/terraform/versions.tf`, `backend.tf`, `variables.tf`, `shared.tf`, `outputs.tf`, `terraform.tfvars.example`
- Create: `deploy/terraform/.terraform.lock.hcl` (generado por `terraform init`)
- Modify: `.gitignore` (agregar `deploy/terraform/.terraform/`, `*.tfstate*`, `*.tfvars` excepto el ejemplo)
- Modify: `.github/workflows/deploy-ci.yml` (job `terraform`, paths)
- Modify: `tests/test_deploy_config.py`

**Interfaces:**
- Produces (para Tasks 4–7): `var.project_id`, `var.region` (default `"southamerica-east1"`), `var.github_repository`
  (default `"collectiveai-team/pomodoro"`), `var.prod_reviewer_users` (`list(string)`, logins), `var.environments`
  (`map(object({ cpu = string, memory = string }))`); `google_service_account.deployer`,
  `google_artifact_registry_repository.pomodoro`, `google_iam_workload_identity_pool_provider.github`,
  `local.image_repository` (`"<region>-docker.pkg.dev/<project>/pomodoro/pomodoro-app"`).

- [ ] **Step 1: Agregar la guarda (falla)**

En `tests/test_deploy_config.py`:

```python
TERRAFORM_DIR = DEPLOY_DIR / "terraform"


@pytest.mark.unit
def test_workload_identity_only_accepts_this_repository() -> None:
    shared = (TERRAFORM_DIR / "shared.tf").read_text()
    # CEL evaluated by Google, so the repository is interpolated into a quoted string literal.
    assert '"assertion.repository == \\"${var.github_repository}\\""' in shared
```

Run: `uv run pytest tests/test_deploy_config.py -q` → 1 FAIL.

- [ ] **Step 2: `versions.tf` y `backend.tf`**

```hcl
# versions.tf
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.9"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}

# Credentials come only from the environment at apply time (docs/deploy.md):
# Google via `gcloud auth application-default login`, NEON_API_KEY, GITHUB_TOKEN.
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "neon" {}

provider "github" {
  owner = split("/", var.github_repository)[0]
}
```

```hcl
# backend.tf
# The bucket is the only resource created by hand (docs/deploy.md, "Bootstrap"):
#   terraform init -backend-config="bucket=<project>-tfstate"
# The state holds Neon connection strings: treat it as a secret.
terraform {
  backend "gcs" {
    prefix = "pomodoro"
  }
}
```

Si `terraform init` no resuelve alguna de esas versiones mayores, fijar la mayor vigente que resuelva y anotarla en el commit.

- [ ] **Step 3: `variables.tf` y `terraform.tfvars.example`**

```hcl
variable "project_id" {
  type        = string
  description = "GCP project that hosts both environments."
}

variable "region" {
  type        = string
  default     = "southamerica-east1"
  description = "Region for Cloud Run, Artifact Registry and Secret Manager replicas."
}

variable "github_repository" {
  type        = string
  default     = "collectiveai-team/pomodoro"
  description = "owner/name of the only repository allowed to deploy through WIF."
}

variable "prod_reviewer_users" {
  type        = list(string)
  description = "GitHub logins that must approve every prod deploy."
}

variable "environments" {
  type = map(object({
    cpu    = string
    memory = string
  }))
  default = {
    qa   = { cpu = "1", memory = "1Gi" }
    prod = { cpu = "1", memory = "1Gi" }
  }
  description = "Per-environment Cloud Run resources."
}
```

```hcl
# terraform.tfvars.example -- copy to terraform.tfvars (gitignored) and fill in.
project_id          = "my-gcp-project"
prod_reviewer_users = ["github-login"]
```

- [ ] **Step 4: `shared.tf` y `outputs.tf`**

```hcl
locals {
  image_repository = "${var.region}-docker.pkg.dev/${var.project_id}/pomodoro/pomodoro-app"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "pomodoro" {
  repository_id = "pomodoro"
  location      = var.region
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_service_account" "deployer" {
  account_id   = "pomodoro-deployer"
  display_name = "Pomodoro CI deployer (GitHub Actions via WIF)"
}

resource "google_artifact_registry_repository_iam_member" "deployer_writer" {
  repository = google_artifact_registry_repository.pomodoro.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.deployer.member
}

# Read-only view of revisions/executions/operations that gcloud polls while deploying.
resource "google_project_iam_member" "deployer_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = google_service_account.deployer.member
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "pomodoro"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  attribute_condition                = "assertion.repository == \"${var.github_repository}\""
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "deployer_wif" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
```

`attribute_condition` es CEL evaluado por Google: la variable se interpola dentro de un literal entre comillas.

```hcl
# outputs.tf
output "image_repository" {
  value = local.image_repository
}

output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_sa" {
  value = google_service_account.deployer.email
}
```

- [ ] **Step 5: `.gitignore`**

Agregar:

```
deploy/terraform/.terraform/
deploy/terraform/*.tfstate*
deploy/terraform/terraform.tfvars
```

- [ ] **Step 6: fmt, init y validate**

```bash
terraform -chdir=deploy/terraform fmt -recursive
terraform -chdir=deploy/terraform init -backend=false
terraform -chdir=deploy/terraform validate
uv run pytest tests/test_deploy_config.py -q
```

Expected: `Success! The configuration is valid.` y las guardas en verde. Commitear `.terraform.lock.hcl`.

- [ ] **Step 7: Job `terraform` en `deploy-ci.yml`**

Agregar `"deploy/terraform/**"` ya queda cubierto por `"deploy/**"`. Agregar el job:

```yaml
  terraform:
    name: terraform
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: deploy/terraform
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_wrapper: false

      - name: terraform fmt
        run: terraform fmt -check -recursive

      - name: terraform init (no backend)
        run: terraform init -backend=false

      - name: terraform validate
        run: terraform validate
```

Run: `uvx zizmor .github/workflows/deploy-ci.yml` → sin hallazgos.

- [ ] **Step 8: Gates y commit**

```bash
prek run --all-files
git add deploy/terraform .gitignore .github/workflows/deploy-ci.yml tests/test_deploy_config.py
git commit -m "feat(deploy): declare shared GCP infrastructure and WIF in Terraform"
```

---

### Task 4: Terraform Neon (proyecto, branches, credenciales por entorno)

**Files:**
- Create: `deploy/terraform/neon.tf`
- Modify: `tests/test_deploy_config.py`

**Interfaces:**
- Consumes: providers de Task 3.
- Produces: `local.database_urls` (`map(string)`, claves `"qa"` y `"prod"`, valores
  `postgresql+psycopg://…?sslmode=require`), marcado sensible.

- [ ] **Step 1: Guarda (falla)**

```python
@pytest.mark.unit
def test_qa_database_has_its_own_role_and_password() -> None:
    """QA must not reuse prod's inherited role: a leaked QA secret must not open prod."""
    neon = (TERRAFORM_DIR / "neon.tf").read_text()
    assert re.search(r'name\s+=\s+"pomodoro_qa"', neon)
    assert "neon_role.qa.password" in neon
    assert "sslmode=require" in neon
```

- [ ] **Step 2: Confirmar el esquema del provider**

```bash
terraform -chdir=deploy/terraform providers schema -json \
  | jq '.provider_schemas["registry.terraform.io/kislerdm/neon"].resource_schemas
        | {project: (.neon_project.block.attributes | keys), endpoint: (.neon_endpoint.block.attributes | keys),
           role: (.neon_role.block.attributes | keys), database: (.neon_database.block.attributes | keys)}'
```

Confirmar que existen `neon_project.database_user/database_password/database_host/database_name/default_branch_id`,
`neon_endpoint.host`, `neon_role.password` y `neon_database.owner_name`. Si algún nombre difiere, usar el real en el Step 3.

- [ ] **Step 3: `neon.tf`**

```hcl
# Neon project with branches prod (default) and qa (child of prod). Each has its own compute
# endpoint that suspends when idle. QA gets its own role and database: a child branch inherits
# prod's roles *with prod's password*, and the provider cannot rotate an inherited role.

resource "neon_project" "pomodoro" {
  name                      = "pomodoro"
  region_id                 = "aws-sa-east-1"
  pg_version                = 17
  history_retention_seconds = 86400

  branch {
    name          = "prod"
    database_name = "pomodoro"
    role_name     = "pomodoro"
  }
}

resource "neon_branch" "qa" {
  project_id = neon_project.pomodoro.id
  parent_id  = neon_project.pomodoro.default_branch_id
  name       = "qa"
}

resource "neon_endpoint" "qa" {
  project_id = neon_project.pomodoro.id
  branch_id  = neon_branch.qa.id
  type       = "read_write"
}

resource "neon_role" "qa" {
  project_id = neon_project.pomodoro.id
  branch_id  = neon_branch.qa.id
  name       = "pomodoro_qa"
}

resource "neon_database" "qa" {
  project_id = neon_project.pomodoro.id
  branch_id  = neon_branch.qa.id
  name       = "pomodoro_qa"
  owner_name = neon_role.qa.name
}

locals {
  database_urls = sensitive({
    prod = "postgresql+psycopg://${neon_project.pomodoro.database_user}:${urlencode(neon_project.pomodoro.database_password)}@${neon_project.pomodoro.database_host}/${neon_project.pomodoro.database_name}?sslmode=require"
    qa   = "postgresql+psycopg://${neon_role.qa.name}:${urlencode(neon_role.qa.password)}@${neon_endpoint.qa.host}/${neon_database.qa.name}?sslmode=require"
  })
}
```

- [ ] **Step 4: fmt, validate, guardas**

```bash
terraform -chdir=deploy/terraform fmt -recursive && terraform -chdir=deploy/terraform validate
uv run pytest tests/test_deploy_config.py -q
```

Expected: valid + verde.

- [ ] **Step 5: Commit**

```bash
prek run --all-files
git add deploy/terraform/neon.tf tests/test_deploy_config.py
git commit -m "feat(deploy): provision Neon prod and qa branches with separate credentials"
```

---

### Task 5: Módulo `environment` (SA, secreto, servicio, job, IAM) e instancias qa/prod

**Files:**
- Create: `deploy/terraform/modules/environment/{main,variables,outputs}.tf`
- Create: `deploy/terraform/environments.tf`
- Modify: `deploy/terraform/outputs.tf`, `tests/test_deploy_config.py`

**Interfaces:**
- Consumes: `local.database_urls`, `local.image_repository`, `google_service_account.deployer`, `var.environments`.
- Produces: `module.environment["qa"|"prod"]` con outputs `service_name`, `service_uri`, `migrate_job_name`.

- [ ] **Step 1: Guardas (fallan)**

```python
@pytest.mark.unit
def test_terraform_never_reverts_the_deployed_image() -> None:
    """Terraform owns the shape, the pipeline owns the image (spec, "Principios")."""
    main = (TERRAFORM_DIR / "modules" / "environment" / "main.tf").read_text()
    assert main.count("ignore_changes") == 2
    assert "template[0].containers[0].image" in main
    assert "template[0].template[0].containers[0].image" in main


@pytest.mark.unit
def test_cloud_run_scales_between_zero_and_one() -> None:
    main = (TERRAFORM_DIR / "modules" / "environment" / "main.tf").read_text()
    assert "min_instance_count = 0" in main
    assert "max_instance_count = 1" in main


@pytest.mark.unit
def test_runtime_identity_reads_only_its_own_secret() -> None:
    main = (TERRAFORM_DIR / "modules" / "environment" / "main.tf").read_text()
    assert "google_secret_manager_secret_iam_member" in main
    assert "google_project_iam_member" not in main
```

- [ ] **Step 2: `modules/environment/variables.tf`**

```hcl
variable "name" {
  type        = string
  description = "Environment name: qa or prod."
}

variable "region" {
  type = string
}

variable "image" {
  type        = string
  description = "Initial image only; deploys change it outside Terraform (ignore_changes)."
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "deployer_member" {
  type        = string
  description = "IAM member of the CI deployer service account."
}

variable "cpu" {
  type = string
}

variable "memory" {
  type = string
}
```

- [ ] **Step 3: `modules/environment/main.tf`**

```hcl
locals {
  prefix = "pomodoro-${var.name}"
}

resource "google_service_account" "runtime" {
  account_id   = "${local.prefix}-run"
  display_name = "Pomodoro ${var.name} runtime"
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${local.prefix}-database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = var.database_url
}

resource "google_secret_manager_secret_iam_member" "runtime_reads_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.runtime.member
}

resource "google_cloud_run_v2_service" "app" {
  name                = local.prefix
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.name == "prod"

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle = true
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      # entrypoint.sh only starts nginx once uvicorn and Next answer, so this passing means all
      # three are up. 20 x 3s leaves room for a cold start.
      startup_probe {
        http_get {
          path = "/api/health"
        }
        period_seconds    = 3
        timeout_seconds   = 2
        failure_threshold = 20
      }

      liveness_probe {
        http_get {
          path = "/api/health"
        }
        period_seconds  = 30
        timeout_seconds = 5
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.runtime_reads_database_url]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.app.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "migrate" {
  name                = "${local.prefix}-migrate"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.runtime.email
      max_retries     = 0
      timeout         = "600s"

      containers {
        image   = var.image
        command = ["/app/backend/scripts/migrate.sh"]

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_secret_manager_secret_iam_member.runtime_reads_database_url]
}

# The deployer may change images and run the job; it cannot touch IAM or the rest of the shape.
resource "google_cloud_run_v2_service_iam_member" "deployer" {
  name     = google_cloud_run_v2_service.app.name
  location = var.region
  role     = "roles/run.developer"
  member   = var.deployer_member
}

resource "google_cloud_run_v2_job_iam_member" "deployer" {
  name     = google_cloud_run_v2_job.migrate.name
  location = var.region
  role     = "roles/run.developer"
  member   = var.deployer_member
}

resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = var.deployer_member
}
```

- [ ] **Step 4: `modules/environment/outputs.tf`, `environments.tf` y outputs raíz**

```hcl
# modules/environment/outputs.tf
output "service_name" {
  value = google_cloud_run_v2_service.app.name
}

output "service_uri" {
  value = google_cloud_run_v2_service.app.uri
}

output "migrate_job_name" {
  value = google_cloud_run_v2_job.migrate.name
}
```

```hcl
# environments.tf
module "environment" {
  source   = "./modules/environment"
  for_each = var.environments

  name            = each.key
  region          = var.region
  image           = "${local.image_repository}:bootstrap"
  database_url    = local.database_urls[each.key]
  deployer_member = google_service_account.deployer.member
  cpu             = each.value.cpu
  memory          = each.value.memory

  depends_on = [google_project_service.apis]
}
```

Agregar a `outputs.tf`:

```hcl
output "service_uris" {
  value = { for name, env in module.environment : name => env.service_uri }
}
```

`var.environments` debe tener exactamente las claves `qa` y `prod` (las de `local.database_urls`). Agregar en
`variables.tf`, dentro de `variable "environments"`:

```hcl
  validation {
    condition     = toset(keys(var.environments)) == toset(["qa", "prod"])
    error_message = "environments must define exactly qa and prod."
  }
```

- [ ] **Step 5: fmt, validate, guardas, commit**

```bash
terraform -chdir=deploy/terraform fmt -recursive && terraform -chdir=deploy/terraform validate
uv run pytest tests/test_deploy_config.py -q
prek run --all-files
git add deploy/terraform tests/test_deploy_config.py
git commit -m "feat(deploy): add the Cloud Run service, migration job and IAM per environment"
```

---

### Task 6: Terraform GitHub (environments, reviewers, variables)

**Files:**
- Create: `deploy/terraform/github.tf`
- Modify: `tests/test_deploy_config.py`

**Interfaces:**
- Consumes: `module.environment[*]`, `google_service_account.deployer`, `google_iam_workload_identity_pool_provider.github`.
- Produces: environments de GitHub `qa` (solo branch `main`) y `prod` (reviewers, solo tags `v*`); variables de repo
  `GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER`, `DEPLOYER_SA`; variables por environment `SERVICE_NAME`, `MIGRATE_JOB_NAME`.

- [ ] **Step 1: Guarda (falla)**

```python
@pytest.mark.unit
def test_prod_environment_requires_reviewers_and_release_tags() -> None:
    github = (TERRAFORM_DIR / "github.tf").read_text()
    assert "reviewers {" in github
    assert re.search(r'tag_pattern\s+=\s+"v\*"', github)
    for name in ("GCP_PROJECT_ID", "GCP_REGION", "WIF_PROVIDER", "DEPLOYER_SA", "SERVICE_NAME", "MIGRATE_JOB_NAME"):
        assert name in github
```

- [ ] **Step 2: `github.tf`**

```hcl
locals {
  github_repository_name = split("/", var.github_repository)[1]
}

data "github_user" "prod_reviewers" {
  for_each = toset(var.prod_reviewer_users)
  username = each.value
}

resource "github_repository_environment" "qa" {
  repository  = local.github_repository_name
  environment = "qa"
  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "qa_main" {
  repository     = local.github_repository_name
  environment    = github_repository_environment.qa.environment
  branch_pattern = "main"
}

resource "github_repository_environment" "prod" {
  repository  = local.github_repository_name
  environment = "prod"
  reviewers {
    users = [for user in data.github_user.prod_reviewers : tonumber(user.id)]
  }
  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment_deployment_policy" "prod_releases" {
  repository     = local.github_repository_name
  environment    = github_repository_environment.prod.environment
  tag_pattern = "v*"
}

# Not secrets: WIF means there are no keys to hide.
resource "github_actions_variable" "shared" {
  for_each = {
    GCP_PROJECT_ID = var.project_id
    GCP_REGION     = var.region
    WIF_PROVIDER   = google_iam_workload_identity_pool_provider.github.name
    DEPLOYER_SA    = google_service_account.deployer.email
  }
  repository    = local.github_repository_name
  variable_name = each.key
  value         = each.value
}

locals {
  github_environments = {
    qa   = github_repository_environment.qa.environment
    prod = github_repository_environment.prod.environment
  }
  environment_variables = merge([
    for name, env in module.environment : {
      "${name}/SERVICE_NAME"     = { environment = local.github_environments[name], name = "SERVICE_NAME", value = env.service_name }
      "${name}/MIGRATE_JOB_NAME" = { environment = local.github_environments[name], name = "MIGRATE_JOB_NAME", value = env.migrate_job_name }
    }
  ]...)
}

resource "github_actions_environment_variable" "per_environment" {
  for_each      = local.environment_variables
  repository    = local.github_repository_name
  environment   = each.value.environment
  variable_name = each.value.name
  value         = each.value.value
}
```

Correr `terraform fmt` (alinea los `=`).

- [ ] **Step 3: fmt, validate, guardas, commit**

```bash
terraform -chdir=deploy/terraform fmt -recursive && terraform -chdir=deploy/terraform validate
uv run pytest tests/test_deploy_config.py -q
prek run --all-files
git add deploy/terraform/github.tf tests/test_deploy_config.py
git commit -m "feat(deploy): manage GitHub environments and Actions variables in Terraform"
```

---

### Task 7: Scripts de deploy, acción compuesta y `deploy.yml`

**Files:**
- Create: `deploy/scripts/deploy-env.sh`, `deploy/scripts/verify-release.sh`
- Create: `.github/actions/deploy-env/action.yml`, `.github/workflows/deploy.yml`
- Modify: `tests/test_deploy_scripts.py`, `tests/test_deploy_config.py`

**Interfaces:**
- Consumes: `smoke.sh` (Task 2); variables de Actions (Task 6).
- Produces: `deploy-env.sh <image>` con env `GCP_REGION`, `SERVICE_NAME`, `MIGRATE_JOB_NAME`; escribe `url=<service-url>`
  en `$GITHUB_OUTPUT` si existe. `verify-release.sh <sha> <image>` sale ≠ 0 si el commit no está en `origin/main` o la
  imagen no existe. Acción `./.github/actions/deploy-env` con inputs `image`, `workload-identity-provider`,
  `service-account`, `region`, `service-name`, `migrate-job-name`; output `url`.

- [ ] **Step 1: Tests de `deploy-env.sh` con un `gcloud` falso (fallan)**

Agregar a `tests/test_deploy_scripts.py`:

```python
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
"""


@pytest.fixture
def fake_gcloud(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gcloud = bin_dir / "gcloud"
    gcloud.write_text(FAKE_GCLOUD)
    gcloud.chmod(0o755)
    return {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GCLOUD_LOG": str(tmp_path / "gcloud.log"),
        "GCP_REGION": "southamerica-east1",
        "SERVICE_NAME": "pomodoro-qa",
        "MIGRATE_JOB_NAME": "pomodoro-qa-migrate",
        "FAIL_ON": "",
        **FAST,
    }


def _calls(env: dict[str, str]) -> list[str]:
    log = Path(env["GCLOUD_LOG"])
    return log.read_text().splitlines() if log.exists() else []


IMAGE = "southamerica-east1-docker.pkg.dev/p/pomodoro/pomodoro-app:abc123"


@pytest.mark.unit
def test_deploy_migrates_then_deploys_without_traffic_then_promotes(
    fake_gcloud: dict[str, str], healthy_app: str
) -> None:
    result = _run("deploy-env.sh", IMAGE, env={**fake_gcloud, "CANDIDATE_URL": healthy_app})
    assert result.returncode == 0, result.stderr
    calls = _calls(fake_gcloud)
    order = [
        next(i for i, c in enumerate(calls) if c.startswith("run jobs update pomodoro-qa-migrate")),
        next(i for i, c in enumerate(calls) if c.startswith("run jobs execute pomodoro-qa-migrate")),
        next(i for i, c in enumerate(calls) if c.startswith("run deploy pomodoro-qa") and "--no-traffic" in c),
        next(i for i, c in enumerate(calls) if c.startswith("run services update-traffic pomodoro-qa --to-latest")),
    ]
    assert order == sorted(order)
    assert "--wait" in calls[order[1]]


@pytest.mark.unit
def test_failed_migration_never_deploys(fake_gcloud: dict[str, str], healthy_app: str) -> None:
    env = {**fake_gcloud, "CANDIDATE_URL": healthy_app, "FAIL_ON": "run jobs execute"}
    result = _run("deploy-env.sh", IMAGE, env=env)
    assert result.returncode != 0
    assert not any(c.startswith("run deploy") for c in _calls(fake_gcloud))


@pytest.mark.unit
def test_failed_smoke_keeps_traffic_on_previous_revision(
    fake_gcloud: dict[str, str], broken_frontend: str
) -> None:
    result = _run("deploy-env.sh", IMAGE, env={**fake_gcloud, "CANDIDATE_URL": broken_frontend})
    assert result.returncode != 0
    assert not any("update-traffic" in c for c in _calls(fake_gcloud))
```

Run: `uv run pytest tests/test_deploy_scripts.py -q` → los 3 nuevos FAIL.

- [ ] **Step 2: `deploy/scripts/deploy-env.sh` (y `chmod +x`)**

```bash
#!/usr/bin/env bash
# Deploy one image to one environment (QA or prod). Usage: deploy-env.sh <image>
# Env: GCP_REGION, SERVICE_NAME, MIGRATE_JOB_NAME.
#   1. point the migration job at the image and run it; stop if it fails;
#   2. deploy a new revision with no traffic, tagged "candidate";
#   3. smoke check the candidate URL; stop if it fails (traffic stays on the previous revision);
#   4. move 100% of traffic to the new revision.
# Migrations must stay backwards compatible (expand/contract): the previous revision keeps
# serving on the migrated schema until step 4.
set -euo pipefail

image="${1:?usage: deploy-env.sh <image>}"
region="${GCP_REGION:?}"
service="${SERVICE_NAME:?}"
job="${MIGRATE_JOB_NAME:?}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "::group::migrate (${job})"
gcloud run jobs update "$job" --region "$region" --image "$image" --quiet
gcloud run jobs execute "$job" --region "$region" --wait --quiet
echo "::endgroup::"

echo "::group::deploy candidate (${service})"
gcloud run deploy "$service" --region "$region" --image "$image" --no-traffic --tag candidate --quiet
candidate_url=$(gcloud run services describe "$service" --region "$region" \
  --format='value(status.traffic.filter(tag=candidate).url)')
echo "::endgroup::"

"$script_dir/smoke.sh" "$candidate_url"

gcloud run services update-traffic "$service" --region "$region" --to-latest --quiet
url=$(gcloud run services describe "$service" --region "$region" --format='value(status.url)')
echo "deployed ${image} to ${url}"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "url=${url}" >>"$GITHUB_OUTPUT"
fi
```

El `FAKE_GCLOUD` del Step 1 distingue las dos lecturas por `status.traffic` y `status.url`, que son las que usa el
script. En el primer deploy real, confirmar que el filtro `status.traffic.filter(tag=candidate).url` devuelve la URL del
tag. Si `gcloud` no soporta esa proyección, cambiar a `--format=json | jq -r '.status.traffic[] | select(.tag=="candidate") | .url'`
y actualizar el patrón del fake.

Run: `uv run pytest tests/test_deploy_scripts.py -q` → todo PASS.

- [ ] **Step 3: Tests de `verify-release.sh` (fallan)**

```python
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo_with_main_and_side(tmp_path: Path) -> tuple[Path, str, str]:
    """A clone whose origin/main has one commit, plus a side commit not on main."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "on main")
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    on_main = _git(clone, "rev-parse", "HEAD")
    _git(clone, "checkout", "-q", "-b", "side")
    _git(clone, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "side")
    return clone, on_main, _git(clone, "rev-parse", "HEAD")


def _verify(repo: Path, sha: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
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
    repo_with_main_and_side: tuple[Path, str, str], fake_gcloud: dict[str, str]
) -> None:
    repo, on_main, _ = repo_with_main_and_side
    assert _verify(repo, on_main, fake_gcloud).returncode == 0


@pytest.mark.unit
def test_verify_release_rejects_a_commit_not_on_main(
    repo_with_main_and_side: tuple[Path, str, str], fake_gcloud: dict[str, str]
) -> None:
    repo, _, side = repo_with_main_and_side
    result = _verify(repo, side, fake_gcloud)
    assert result.returncode != 0
    assert "not on main" in result.stderr


@pytest.mark.unit
def test_verify_release_rejects_a_missing_image(
    repo_with_main_and_side: tuple[Path, str, str], fake_gcloud: dict[str, str]
) -> None:
    repo, on_main, _ = repo_with_main_and_side
    result = _verify(repo, on_main, {**fake_gcloud, "FAIL_ON": "artifacts docker images describe"})
    assert result.returncode != 0
    assert "no image" in result.stderr
```

Run: `uv run pytest tests/test_deploy_scripts.py -q` → 3 FAIL.

- [ ] **Step 4: `deploy/scripts/verify-release.sh` (y `chmod +x`)**

```bash
#!/usr/bin/env bash
# Guard before a prod deploy: the release commit must be on main (so it went through QA) and its
# image must already exist. Prod never rebuilds. Usage: verify-release.sh <sha> <image>
set -euo pipefail

sha="${1:?usage: verify-release.sh <sha> <image>}"
image="${2:?usage: verify-release.sh <sha> <image>}"

if ! git merge-base --is-ancestor "$sha" origin/main; then
  echo "verify-release: ${sha} is not on main" >&2
  exit 1
fi
if ! gcloud artifacts docker images describe "$image" --quiet >/dev/null; then
  echo "verify-release: no image ${image}; it is built on every push to main" >&2
  exit 1
fi
echo "verify-release: ${sha} is on main and ${image} exists"
```

Run: `uv run pytest tests/test_deploy_scripts.py -q` → todo PASS.

- [ ] **Step 5: `.github/actions/deploy-env/action.yml`**

```yaml
name: deploy-env
description: Authenticate through WIF and run deploy/scripts/deploy-env.sh for one environment.

inputs:
  image:
    required: true
  workload-identity-provider:
    required: true
  service-account:
    required: true
  region:
    required: true
  service-name:
    required: true
  migrate-job-name:
    required: true

outputs:
  url:
    value: ${{ steps.deploy.outputs.url }}

runs:
  using: composite
  steps:
    - uses: google-github-actions/auth@v3
      with:
        workload_identity_provider: ${{ inputs.workload-identity-provider }}
        service_account: ${{ inputs.service-account }}

    - uses: google-github-actions/setup-gcloud@v3

    - id: deploy
      shell: bash
      env:
        IMAGE: ${{ inputs.image }}
        GCP_REGION: ${{ inputs.region }}
        SERVICE_NAME: ${{ inputs.service-name }}
        MIGRATE_JOB_NAME: ${{ inputs.migrate-job-name }}
      run: deploy/scripts/deploy-env.sh "$IMAGE"
```

- [ ] **Step 6: `.github/workflows/deploy.yml`**

```yaml
name: deploy

# Cloud Run deploy (docs/deploy.md). Every push to main builds the image once and deploys it to
# QA; publishing a GitHub Release promotes that same image to prod after a reviewer approves.
# main's branch protection requires the CI checks, so a push to main is already green.

on:
  push:
    branches: [main]
  release:
    types: [published]

permissions: {}

env:
  IMAGE_REPOSITORY: ${{ vars.GCP_REGION }}-docker.pkg.dev/${{ vars.GCP_PROJECT_ID }}/pomodoro/pomodoro-app

jobs:
  build:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    outputs:
      image: ${{ steps.image.outputs.image }}
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false

      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.WIF_PROVIDER }}
          service_account: ${{ vars.DEPLOYER_SA }}

      - uses: google-github-actions/setup-gcloud@v3

      - id: image
        run: echo "image=${IMAGE_REPOSITORY}:${GITHUB_SHA}" >>"$GITHUB_OUTPUT"

      - name: Build and push
        env:
          IMAGE: ${{ steps.image.outputs.image }}
          REGISTRY: ${{ vars.GCP_REGION }}-docker.pkg.dev
        run: |
          gcloud auth configure-docker "$REGISTRY" --quiet
          docker build -f deploy/Dockerfile -t "$IMAGE" .
          docker push "$IMAGE"

  deploy-qa:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: qa
      url: ${{ steps.deploy.outputs.url }}
    concurrency:
      group: deploy-qa
      cancel-in-progress: false
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false

      - id: deploy
        uses: ./.github/actions/deploy-env
        with:
          image: ${{ needs.build.outputs.image }}
          workload-identity-provider: ${{ vars.WIF_PROVIDER }}
          service-account: ${{ vars.DEPLOYER_SA }}
          region: ${{ vars.GCP_REGION }}
          service-name: ${{ vars.SERVICE_NAME }}
          migrate-job-name: ${{ vars.MIGRATE_JOB_NAME }}

  deploy-prod:
    if: github.event_name == 'release'
    runs-on: ubuntu-latest
    environment:
      name: prod
      url: ${{ steps.deploy.outputs.url }}
    concurrency:
      group: deploy-prod
      cancel-in-progress: false
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
          fetch-depth: 0

      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.WIF_PROVIDER }}
          service_account: ${{ vars.DEPLOYER_SA }}

      - uses: google-github-actions/setup-gcloud@v3

      - id: image
        run: echo "image=${IMAGE_REPOSITORY}:${GITHUB_SHA}" >>"$GITHUB_OUTPUT"

      - name: Verify the release commit and image
        env:
          IMAGE: ${{ steps.image.outputs.image }}
        run: deploy/scripts/verify-release.sh "$GITHUB_SHA" "$IMAGE"

      - id: deploy
        uses: ./.github/actions/deploy-env
        with:
          image: ${{ steps.image.outputs.image }}
          workload-identity-provider: ${{ vars.WIF_PROVIDER }}
          service-account: ${{ vars.DEPLOYER_SA }}
          region: ${{ vars.GCP_REGION }}
          service-name: ${{ vars.SERVICE_NAME }}
          migrate-job-name: ${{ vars.MIGRATE_JOB_NAME }}
```

En un evento `release`, `GITHUB_SHA` es el commit del tag del release.

- [ ] **Step 7: Guardas estáticas del workflow**

Agregar a `tests/test_deploy_config.py`:

```python
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


@pytest.mark.unit
def test_prod_deploy_never_builds_an_image() -> None:
    deploy = (WORKFLOWS / "deploy.yml").read_text()
    prod_job = deploy.split("  deploy-prod:", 1)[1]
    assert "docker build" not in prod_job
    assert "verify-release.sh" in prod_job


@pytest.mark.unit
def test_deploy_workflow_has_no_default_permissions_and_never_cancels_a_deploy() -> None:
    deploy = (WORKFLOWS / "deploy.yml").read_text()
    assert "\npermissions: {}\n" in deploy
    assert deploy.count("cancel-in-progress: false") == 2
    assert "cancel-in-progress: true" not in deploy
```

Run: `uv run pytest tests/test_deploy_config.py tests/test_deploy_scripts.py -q` → PASS.

- [ ] **Step 8: Auditar y commitear**

```bash
uvx zizmor .github/workflows/deploy.yml .github/actions/deploy-env/action.yml
prek run --all-files
git add deploy/scripts .github/actions/deploy-env .github/workflows/deploy.yml tests/test_deploy_scripts.py tests/test_deploy_config.py
git commit -m "ci(deploy): build on main, deploy to QA and promote releases to prod"
```

zizmor no debe reportar `template-injection` (todo valor dinámico pasa por `env:`). Si reporta `excessive-permissions` o
`use-trusted-publishing` sobre algo intencional, documentarlo en `.github/zizmor.yml` con su motivo, como las entradas
existentes.

---

### Task 8: Documentación (README, runbook, ADR-0004)

**Files:**
- Modify: `README.md`
- Create: `docs/deploy.md`, `docs/adr/0004-single-container-nginx-cloud-run.md`
- Modify: `tests/test_deploy_config.py`

**Interfaces:**
- Consumes: nombres de recursos, scripts y workflows de Tasks 1–7.

- [ ] **Step 1: Guarda (falla)**

```python
@pytest.mark.unit
def test_runbook_covers_every_operation_the_spec_lists() -> None:
    runbook = (REPO_ROOT / "docs" / "deploy.md").read_text()
    for heading in (
        "## Bootstrap",
        "## Primer apply",
        "## Primer deploy",
        "## Verificación del rate limit en QA",
        "## Promoción a prod",
        "## Rollback manual",
        "## Reset de QA desde prod",
        "## Rotación de secretos y tokens",
        "## Subir max-instances",
    ):
        assert heading in runbook
```

- [ ] **Step 2: `README.md`**

Reemplazar el contenido por:

````markdown
# pomodoro

Pomodoro Collective: Next.js (`frontend/`) + FastAPI (`backend/`) + PostgreSQL/SQLite.

## Levantar la app

### Con Docker Compose (tipo producción)

```bash
docker compose up --build
```

Abre http://localhost:3000. Levanta Postgres, corre las migraciones y arranca backend y frontend por separado.

Para probar la imagen única que corre en Cloud Run (nginx + Next + uvicorn):

```bash
docker compose -f docker-compose.app.yml up --build
```

Abre http://localhost:8080.

### Desarrollo local (SQLite)

```bash
uv sync
mkdir -p .tmp && uv run alembic upgrade head   # crea .tmp/pomodoro.db
uv run pomodoro-api                            # http://127.0.0.1:8000

cd frontend && pnpm install && pnpm dev        # http://localhost:3000, /api/* va al backend
```

## Tests

```bash
uv run pytest -m "not integration"   # backend unit + guardas
cd frontend && pnpm test             # frontend
```

Los tests de integración con Postgres (`-m integration`), el E2E con Playwright (`e2e/`) y los de la imagen única
(`tests/test_app_image.py`) corren en CI; ver `.github/workflows/`.

## Deploy

QA se despliega solo en cada merge a `main`. Prod se despliega al publicar un GitHub Release (tag `v*`), con aprobación.
Infraestructura en `deploy/terraform/`. Procedimientos en [docs/deploy.md](docs/deploy.md); decisión de arquitectura en
[ADR-0004](docs/adr/0004-single-container-nginx-cloud-run.md).
````

- [ ] **Step 3: `docs/deploy.md` (runbook)**

Escribir con estas secciones y este contenido mínimo:

- `## Arquitectura`: un párrafo y el diagrama del spec; servicios, jobs, secretos y SAs (nombres de Global Constraints).
- `## Prerequisitos`: `gcloud`, `terraform >= 1.9`, `jq`, cuenta Neon con API key, token de GitHub con admin del repo; la
  protección de `main` debe exigir los checks `gates`, `unit (SQLite)`, `integration (PostgreSQL)`, `smoke (docker compose)`,
  `app-image`, `terraform`.
- `## Bootstrap`:
  ```bash
  gcloud auth application-default login
  gcloud storage buckets create "gs://${PROJECT_ID}-tfstate" --location=southamerica-east1 --uniform-bucket-level-access
  gcloud storage buckets update "gs://${PROJECT_ID}-tfstate" --versioning
  cd deploy/terraform && cp terraform.tfvars.example terraform.tfvars   # completar
  terraform init -backend-config="bucket=${PROJECT_ID}-tfstate"
  ```
- `## Primer apply`: en tres pasos, porque los servicios necesitan una imagen existente:
  ```bash
  export NEON_API_KEY=...  GITHUB_TOKEN=...       # solo en esta shell, nunca en archivos
  terraform apply -target=google_project_service.apis -target=google_artifact_registry_repository.pomodoro
  REPO=$(terraform output -raw image_repository)
  gcloud auth configure-docker southamerica-east1-docker.pkg.dev
  docker build -f ../Dockerfile -t "$REPO:bootstrap" ../.. && docker push "$REPO:bootstrap"
  terraform plan -out=tfplan   # revisar
  terraform apply tfplan
  ```
  Aclarar que `bootstrap` arranca sin migraciones (el health no toca la base) y que el primer deploy migra.
- `## Primer deploy`: merge a `main` → workflow `deploy` → `build` + `deploy-qa`; URL en el environment `qa` o en
  `terraform output service_uris`.
- `## Verificación del rate limit en QA`: después del primer deploy, 5 logins fallidos contra un email de prueba con un
  `X-Forwarded-For` distinto en cada uno y el sexto debe dar 429:
  ```bash
  for i in 1 2 3 4 5 6; do
    curl -s -o /dev/null -w '%{http_code}\n' -H "X-Forwarded-For: 198.51.100.$i" \
      -H 'Content-Type: application/json' -d '{"email":"ratelimit@example.com","password":"wrong"}' \
      "$QA_URL/api/auth/login"
  done   # esperado: 401 x5, luego 429
  ```
  Si no da 429: aplicar el plan B del spec (nginx reemplaza `X-Forwarded-For` en lugar de agregar) y repetir. Anotar el
  resultado y la fecha en esta sección.
- `## Promoción a prod`: crear un Release con tag `vX.Y.Z` sobre un commit de `main` que ya pasó por QA; aprobar el job
  `deploy-prod`; qué hace `verify-release.sh`.
- `## Rollback manual`:
  ```bash
  gcloud run revisions list --service pomodoro-prod --region southamerica-east1
  gcloud run services update-traffic pomodoro-prod --region southamerica-east1 --to-revisions <revision>=100
  ```
  Avisar que el próximo deploy vuelve a `--to-latest`, y que las migraciones no se revierten: por eso deben ser
  compatibles hacia atrás (expand/contract).
- `## Reset de QA desde prod`: QA usa rol y base propios (`pomodoro_qa`), así que se copian datos, no la branch:
  ```bash
  pg_dump --format=custom --no-owner "$PROD_URL" > prod.dump
  pg_restore --clean --if-exists --no-owner --role=pomodoro_qa --dbname "$QA_URL" prod.dump
  rm prod.dump
  ```
  Los URLs en formato libpq (`postgresql://…?sslmode=require`, sin `+psycopg`) se leen de Secret Manager con
  `gcloud secrets versions access latest --secret ...`; no pegarlos en la shell history (usar `read -s`).
- `## Rotación de secretos y tokens`: password de Neon (`neon_role`/proyecto: reset en la consola de Neon y luego
  `terraform apply -replace=...` del recurso que expone el password, o reset + `apply` para que se regrabe el secreto);
  nueva versión del secreto ⇒ redeploy para que la tome (`version = "latest"` se resuelve al arrancar la instancia);
  `NEON_API_KEY` y `GITHUB_TOKEN`: revocar después del `apply` si son de uso único.
- `## Subir max-instances`: requiere rate limit compartido (hoy en memoria, correcto solo con una instancia); fuera de
  alcance hasta moverlo a un almacenamiento compartido.
- `## Costos y arranque en frío`: min 0 en Cloud Run y autosuspend en Neon; si el arranque en frío molesta, `min_instance_count = 1`
  en prod (con costo).

- [ ] **Step 4: `docs/adr/0004-single-container-nginx-cloud-run.md`**

Seguir el formato de `docs/adr/0001-nextjs-fastapi-web-app.md` (leerlo primero). Contenido:
- **Contexto:** issue #12 pedía dos imágenes; Cloud Run con min 0 / max 1 y dos entornos; un solo origen evita CORS y cookies
  cross-site; el rate limit en memoria exige una sola instancia del backend.
- **Decisión:** una imagen con nginx (`$PORT`) + Next standalone + uvicorn en loopback; `tini` + `entrypoint.sh` con
  `wait -n`; migraciones en un Cloud Run Job.
- **Alternativas:** dos servicios Cloud Run (CORS/cookies, dos arranques en frío, dos límites de instancias); sidecars
  multi-contenedor (más configuración, el mismo resultado).
- **Consecuencias:** los Dockerfiles separados y `docker-compose.yml` siguen para local; un proceso que muere reinicia la
  instancia entera; escalar el backend independiente del frontend requiere revisar esta decisión. Relación con ADR-0001
  (se mantiene la separación Next/FastAPI; solo cambia el empaquetado).

- [ ] **Step 5: Guarda y commit**

```bash
uv run pytest tests/test_deploy_config.py -q
prek run --all-files
git add README.md docs/deploy.md docs/adr/0004-single-container-nginx-cloud-run.md tests/test_deploy_config.py
git commit -m "docs: document running, testing and deploying Pomodoro on Cloud Run"
```

---

### Cierre

- [ ] `uv run pytest -m "not integration" -q` en verde; `docker compose -f docker-compose.app.yml up --build --wait` +
  `tests/test_app_image.py` en verde; `terraform validate` en verde; `prek run --all-files` en verde.
- [ ] Push de `feat/cloud-run-deploy` y PR contra `main`. `deploy-ci` debe pasar. `deploy.yml` no corre en PRs.
- [ ] El `terraform apply` real y el primer deploy los ejecuta una persona siguiendo `docs/deploy.md`; no forman parte del PR.
