# Deploy de Pomodoro Collective en Google Cloud Run (QA y prod)

- Fecha: 2026-10-07
- Estado: propuesta para revisión
- Depende de: PR #14 (implementación del issue #12)

## Objetivo

Desplegar la web app (frontend Next.js + backend FastAPI + PostgreSQL) en Google Cloud Run en dos entornos, **QA** y **prod**,
con **mínimo 0 y máximo 1 instancia**, de modo que:

- cada merge a `main` quede desplegado en QA sin intervención;
- prod reciba exactamente la misma imagen que pasó por QA, cuando se publica un release y alguien lo aprueba;
- toda la infraestructura esté declarada en el repo (Terraform) y sea reproducible;
- el costo en reposo sea mínimo (Cloud Run y la base escalan a cero).

### Decisiones tomadas en la conversación

| Tema | Decisión |
|---|---|
| Base de datos | Postgres serverless externo: **Neon** |
| Proyectos GCP | **Un proyecto** con los dos entornos |
| Disparadores | **QA automático** en cada merge a `main`; **prod por GitHub Release** con aprobación manual |
| URLs | Las `*.run.app` de Cloud Run; dominio propio fuera de alcance |
| Topología | **Un solo contenedor** por entorno con **nginx** como entrada, Next.js y uvicorn adentro |
| Aprovisionamiento | **Terraform** para GCP, Neon y GitHub |

## Arquitectura de runtime

### Servicios

En el proyecto GCP, región `southamerica-east1`:

- Servicio Cloud Run `pomodoro-qa` y servicio Cloud Run `pomodoro-prod`.
- Cada uno corre **un contenedor** con la imagen `pomodoro-app`.
- Escalado `min-instances=0`, `max-instances=1`, CPU asignada solo durante los requests (default), concurrencia default.
- Recursos iniciales: 1 vCPU y 1 GiB de memoria (ajustables por variable de Terraform).
- Acceso público (`roles/run.invoker` para `allUsers`) en la URL `*.run.app`.
- Startup probe y liveness probe HTTP sobre `/api/health`.

### Contenedor único

```
Cloud Run ($PORT) ──► nginx ──┬── /api/*  ──► uvicorn 127.0.0.1:8000 (FastAPI)
                              └── /*      ──► node    127.0.0.1:3000 (Next.js standalone)
```

- **nginx** escucha en `$PORT` (Cloud Run inyecta 8080). Rutea `/api/` a uvicorn y el resto a Next. Pasa `Host`,
  `X-Forwarded-Proto` y `X-Forwarded-For` (`$proxy_add_x_forwarded_for`).
- **uvicorn** escucha solo en `127.0.0.1:8000`, con la confianza de proxy por defecto (`127.0.0.1`).
- **Next.js** standalone escucha solo en `127.0.0.1:3000`. En producción el ruteo de `/api` lo hace nginx, así que no
  participa `frontend/proxy.ts`. Sigue sirviendo para el desarrollo local y para `docker compose`.
- **Proceso principal**: `tini` como PID 1 y un `entrypoint.sh` que arranca uvicorn, Next y nginx, y termina con error
  apenas cualquiera de los tres sale (`wait -n`), para que Cloud Run reinicie la instancia. Señales `SIGTERM` propagadas a los tres.
- **Imagen**: `deploy/Dockerfile`, multi-stage, que reutiliza los builds existentes: venv del backend con uv, `next build`
  standalone y una base con Python, Node y nginx. Corre como usuario no root.
- Los Dockerfiles separados (`backend/Dockerfile`, `frontend/Dockerfile`) y el `docker-compose.yml` actual se mantienen para
  el entorno local "tipo producción". Se agrega `docker-compose.app.yml` que levanta la imagen única contra un Postgres local,
  para probarla tal como corre en Cloud Run.

Esto se aparta del issue #12, que pedía "desplegar dos imágenes Docker (frontend y backend)". El cambio queda registrado en
**ADR-0004** (`docs/adr/0004-single-container-nginx-cloud-run.md`).

### Base de datos (Neon)

- Un proyecto Neon `pomodoro` en la región más cercana disponible (`aws-sa-east-1`), con branches `prod` (principal) y
  `qa` (hija de `prod`).
- Cada branch tiene su endpoint de cómputo con autosuspend (escala a cero) y su rol y base `pomodoro`.
- La conexión es `postgresql+psycopg://…@<host>/pomodoro?sslmode=require`. No hace falta cambiar la app.
- La branch `qa` se puede resetear desde `prod` (procedimiento en el runbook) cuando se necesiten datos realistas.

### Secretos y configuración

- Secret Manager: `pomodoro-qa-database-url` y `pomodoro-prod-database-url`. Terraform escribe el valor desde el provider de Neon.
- El servicio y el job de cada entorno reciben `DATABASE_URL` como variable montada desde su secreto.
- Service accounts de runtime: `pomodoro-qa-run` y `pomodoro-prod-run`, cada una con `secretAccessor` **solo** sobre su secreto.

### Migraciones

- Cloud Run Jobs `pomodoro-qa-migrate` y `pomodoro-prod-migrate`, con la misma imagen y comando `backend/scripts/migrate.sh`,
  con la SA y el secreto del entorno.
- Se ejecutan en cada deploy **antes** de actualizar el servicio. Si la migración falla, el deploy se corta y el servicio
  queda en la revisión anterior. Las migraciones nunca corren al arrancar el contenedor.

### Rate limiting e IP del cliente

El backend confía en `127.0.0.1` (nginx). Por eso, a diferencia de la topología de `docker compose`, vuelve a leer
`X-Forwarded-For`. uvicorn toma la **última** dirección no confiable de la lista. Detrás de Cloud Run esa es la que agrega la
infraestructura de Google, no la que pueda mandar el cliente. Esto es un supuesto y **hay que verificarlo**:

- test automatizado con la imagen única: un `X-Forwarded-For` falsificado y distinto en cada intento igual recibe 429 al sexto
  login fallido;
- verificación en QA después del primer deploy: el mismo escenario contra la URL real.

Si la verificación en QA falla, nginx deja de reenviar el `X-Forwarded-For` del cliente y lo reemplaza por la dirección que
agregó Google, y se repite la verificación.

Con `max-instances=1` el rate limit en memoria es correcto. Subir el máximo requiere moverlo a un almacenamiento compartido
(fuera de alcance).

## CI/CD (GitHub Actions)

### Autenticación

Workload Identity Federation, sin claves JSON:

- un pool y un provider que aceptan solo tokens OIDC del repo `collectiveai-team/pomodoro`;
- una SA `pomodoro-deployer`, impersonable desde ese provider, con `artifactregistry.writer` sobre el repositorio,
  `run.developer` sobre los servicios y jobs, `iam.serviceAccountUser` sobre las dos SAs de runtime y permiso para ejecutar
  los jobs. **No** tiene permisos para modificar IAM ni infraestructura.

### Workflow `deploy.yml`

1. **build**: en cada push a `main` con el CI en verde, construye `deploy/Dockerfile` y publica
   `<region>-docker.pkg.dev/<project>/pomodoro/pomodoro-app:<sha>`.
2. **deploy-qa** (GitHub Environment `qa`, automático):
   1. actualiza la imagen del job `pomodoro-qa-migrate` a `<sha>` y lo ejecuta con `--wait`; si falla, corta;
   2. `gcloud run deploy pomodoro-qa --image …:<sha>`, cambiando **solo la imagen**: el resto de la configuración es de Terraform;
   3. smoke check: `GET /api/health` = 200 y `GET /login` = 200;
   4. si el smoke check falla, devuelve el 100% del tráfico a la revisión anterior y el job falla.
3. **deploy-prod** (GitHub Environment `prod`, con reviewers obligatorios), al publicar un GitHub Release:
   - resuelve el SHA del tag y verifica que `pomodoro-app:<sha>` exista en Artifact Registry. **No reconstruye.**
   - repite migración, deploy, smoke check y rollback contra prod.

El workflow usa acciones fijadas por tag (política del `zizmor.yml`), `permissions` mínimos por job (`id-token: write` solo
donde se autentica) y `concurrency` por entorno, para que dos deploys no se pisen.

### CI de PRs

- Job nuevo `app-image`: construye `deploy/Dockerfile`, lo levanta con `docker-compose.app.yml` y corre los tests de la imagen única.
- `terraform fmt -check` y `terraform validate` sobre `deploy/terraform`.

## Infraestructura (Terraform)

### Estructura

```
deploy/terraform/
  versions.tf        # providers: google, neon (kislerdm/neon), github (integrations/github)
  backend.tf         # state en GCS
  shared.tf          # APIs, Artifact Registry, WIF, SA deployer
  neon.tf            # proyecto Neon, branches prod/qa, endpoints, roles, bases
  github.tf          # Environments qa/prod, reviewers de prod, variables de Actions
  environments.tf    # module "qa" y module "prod"
  modules/environment/
    main.tf          # SA runtime, secreto DATABASE_URL, servicio Cloud Run, job de migraciones, IAM
    variables.tf
    outputs.tf       # URL del servicio
  terraform.tfvars.example
```

### Principios

- **Terraform es dueño de la forma, el pipeline es dueño de la imagen.** El servicio y el job declaran
  `lifecycle { ignore_changes = [<image>] }` para que un `apply` no revierta la versión desplegada. En el primer `apply` se usa
  una imagen inicial (`pomodoro-app:bootstrap`), que el primer deploy reemplaza.
- **Aplica una persona, no el CI.** `terraform plan/apply` se corre a mano cuando cambia la infraestructura. La SA del pipeline
  no tiene permisos de infraestructura.
- **State**: bucket GCS `<project>-tfstate` con versionado y acceso uniforme, legible y escribible solo por quienes aplican. El
  state contiene los connection strings de Neon, así que se trata como sensible. Es el único recurso creado a mano antes del
  primer `apply` (comando documentado en el runbook).
- **Credenciales de providers** solo por variables de entorno en el momento del `apply`: `NEON_API_KEY` y `GITHUB_TOKEN` (con
  admin del repo para Environments). Las de Google, por `gcloud auth application-default login`. Nada se commitea.
- **Variables**: `project_id`, `region`, `github_repo`, `prod_reviewers` (usuarios o equipos de GitHub), recursos por entorno.

### Lo que gestiona el provider de GitHub

- Environments `qa` (sin reviewers) y `prod` (reviewers = `prod_reviewers`, solo desde releases).
- Variables de Actions por environment: `GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER`, `DEPLOYER_SA`, `SERVICE_NAME`,
  `MIGRATE_JOB_NAME`. No son secretos: WIF evita las claves.

## Documentación

- `README.md`: cómo levantar la app (Docker Compose y desarrollo local con SQLite), cómo correr los tests y un resumen del deploy
  con un link al runbook.
- `docs/deploy.md` (runbook): prerequisitos y bootstrap del state, primer `terraform apply`, primer deploy, promoción a prod,
  rollback manual, reset de la branch QA de Neon, rotación de secretos y tokens, y cómo subir `max-instances` y qué implica.
- `docs/adr/0004-single-container-nginx-cloud-run.md`: decisión de imagen única con nginx y relación con ADR-0001 y el issue #12.

## Verificación

- **Imagen única** (CI de PRs, con `docker-compose.app.yml`):
  - `GET /` sirve el frontend y `GET /api/health` el backend, a través de nginx;
  - flujo registro → login → `GET /api/auth/me` con la cookie de sesión;
  - si uvicorn o Next mueren, el contenedor termina (código distinto de 0);
  - rate limit: `X-Forwarded-For` falsificado y rotativo, 429 al sexto intento.
- **Terraform**: `fmt -check` y `validate` en CI; `plan` revisado a mano antes de cada `apply`.
- **Deploy**: smoke check con rollback automático en QA y prod; verificación manual del rate limit en QA después del primer deploy.

## Fuera de alcance

- Dominio propio y certificados.
- Monitoreo, alertas y dashboards más allá de lo que trae Cloud Run.
- Backups de Neon más allá de los incluidos en el plan elegido.
- Más de una instancia (requiere rate limit compartido).
- Entornos efímeros por PR.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El `X-Forwarded-For` en Cloud Run no se comporta como se supone y reabre el bypass del rate limit | Test con la imagen única y verificación en QA. Plan B: nginx reemplaza el header |
| Arranque en frío lento (tres procesos y la base de Neon despertando) | Medirlo en QA. Si molesta, `min-instances=1` en prod (con costo) o el autosuspend de Neon más largo |
| El state de Terraform tiene secretos | Bucket con acceso restringido y versionado. Nadie más lo lee |
| Tokens de Neon y GitHub con permisos amplios | Solo en el momento del `apply`, nunca en CI ni commiteados. Rotación documentada |
| Una migración incompatible rompe la revisión anterior durante el rollback | Las migraciones deben ser compatibles hacia atrás (expand/contract). Queda documentado en el runbook |
