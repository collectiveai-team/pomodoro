# syntax=docker/dockerfile:1
#
# Production image for the FastAPI backend (uvicorn). Build context is the repo
# root (the uv workspace root), not backend/, because pyproject.toml/uv.lock/
# alembic.ini live there:
#
#   docker build -f backend/Dockerfile -t pomodoro-backend .
#
# Alembic migrations are intentionally NOT run on container start (Despliegue
# section, issue #12) -- run backend/scripts/migrate.sh as its own deploy step,
# e.g. `docker run --rm -e DATABASE_URL=... pomodoro-backend backend/scripts/migrate.sh`.

ARG PYTHON_VERSION=3.14-slim-bookworm

FROM ghcr.io/astral-sh/uv:0.11.12 AS uv

FROM python:${PYTHON_VERSION} AS base
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

# ---- builder: resolve dependencies from the lockfile, then add the source ----
# The project itself is never built/installed (--no-install-project): its
# version is derived from git tags via hatch-vcs, and the image has no .git.
# The `pomodoro` package is run straight from the copied source tree via
# PYTHONPATH instead, so dependency resolution never needs git history.
FROM base AS builder
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev
COPY alembic.ini ./
COPY backend ./backend

# ---- runtime: copy the resolved venv + source, drop root ----
FROM python:${PYTHON_VERSION} AS runtime
RUN groupadd --system --gid 1000 pomodoro \
    && useradd --system --uid 1000 --gid pomodoro --home-dir /app pomodoro
WORKDIR /app
RUN chown pomodoro:pomodoro /app
COPY --from=builder --chown=pomodoro:pomodoro /app /app
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/backend" \
    PYTHONUNBUFFERED=1

USER 1000:1000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "pomodoro.entrypoints.app:app", "--host", "0.0.0.0", "--port", "8000"]
