# Backend image: FastAPI under uvicorn (ADR-0001). The build context is the repository root so
# the lockfile, alembic.ini and backend/ are all reachable. The same image runs the explicit
# `alembic upgrade head` deploy step (ADR-0002); the app never migrates at startup.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/backend \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY backend/alembic ./backend/alembic
COPY backend/pomodoro ./backend/pomodoro

RUN useradd --system --no-create-home --uid 10001 app
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]

CMD ["uvicorn", "pomodoro.entrypoints.app:app", "--host", "0.0.0.0", "--port", "8000"]
