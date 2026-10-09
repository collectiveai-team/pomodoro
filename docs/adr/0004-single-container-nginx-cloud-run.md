# Una sola imagen (nginx + Next.js + FastAPI) en Cloud Run

El issue #12 pedía dos imágenes (frontend y backend). Para Cloud Run, con mínimo 0 y máximo 1 instancia y dos entornos (QA y prod), elegimos una sola imagen por entorno (`deploy/Dockerfile`): nginx escucha en `$PORT` y rutea `/api/*` a uvicorn y el resto a Next.js standalone, ambos en `127.0.0.1`. Un solo origen mantiene la cookie de sesión como first-party, sin CORS ni `SameSite=None`, igual que en ADR-0001. Además, el rate limit del login vive en memoria y solo es correcto con una única instancia del backend; una sola unidad de despliegue lo hace explícito.

`tini` es PID 1 y `deploy/entrypoint.sh` arranca los tres procesos, espera a que uvicorn y Next respondan antes de levantar nginx, y termina con error apenas uno sale (`wait -n`) para que Cloud Run reemplace la instancia. `SIGTERM` se propaga a los tres. La imagen nunca migra al arrancar: las migraciones corren en un Cloud Run Job (`pomodoro-<env>-migrate`) antes de mover el tráfico.

## Considered Options

- **Dos servicios Cloud Run (frontend y backend)**: obliga a resolver CORS y cookies cross-site, duplica los arranques en frío y los límites de instancias.
- **Un servicio con contenedores sidecar**: más configuración para el mismo resultado; nginx seguiría siendo necesario como entrada.

## Consequences

- `backend/Dockerfile`, `frontend/Dockerfile` y `docker-compose.yml` siguen existiendo para el entorno local "tipo producción"; `docker-compose.app.yml` prueba la imagen única.
- Si un proceso muere, se reinicia la instancia completa (frontend y backend juntos).
- Escalar el backend de forma independiente del frontend, o subir `max-instances`, obliga a revisar esta decisión (y a mover el rate limit a un almacenamiento compartido).
- Relación con ADR-0001: se mantiene la separación Next.js / FastAPI y el mismo origen; solo cambia el empaquetado (la línea "dos imágenes" de sus consecuencias queda superada para Cloud Run).
