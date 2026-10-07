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
