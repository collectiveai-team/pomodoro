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
