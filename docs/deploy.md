# Deploy en Google Cloud Run (QA y prod)

Runbook operativo. Diseño y decisiones: `docs/superpowers/specs/2026-10-07-cloud-run-deploy-design.md` y
[ADR-0004](adr/0004-single-container-nginx-cloud-run.md). La fuente de verdad de nombres y comandos es el código en
`deploy/`, `.github/workflows/deploy.yml` y `.github/actions/deploy-env/`.

## Arquitectura

```
Cloud Run ($PORT) ──► nginx ──┬── /api/*  ──► uvicorn 127.0.0.1:8000 (FastAPI)
                              └── /*      ──► node    127.0.0.1:3000 (Next.js standalone)
```

Un proyecto GCP, región `southamerica-east1`, dos entornos con escalado 0 a 1 instancia:

| Recurso | QA | prod |
|---|---|---|
| Servicio Cloud Run | `pomodoro-qa` | `pomodoro-prod` |
| Job de migraciones | `pomodoro-qa-migrate` | `pomodoro-prod-migrate` |
| Secreto `DATABASE_URL` | `pomodoro-qa-database-url` | `pomodoro-prod-database-url` |
| SA de runtime | `pomodoro-qa-run` | `pomodoro-prod-run` |
| Base en Neon | branch `qa`, rol y base `pomodoro_qa` | branch `prod`, rol y base `pomodoro` |

Compartido: repositorio de Artifact Registry `pomodoro` (imagen `pomodoro-app`, tag = SHA del commit), SA
`pomodoro-deployer` y un Workload Identity Pool que solo acepta el repositorio `collectiveai-team/pomodoro`.
Terraform (`deploy/terraform/`) declara GCP, Neon y los GitHub Environments y variables de Actions.

Los prereleases de GitHub no se despliegan a prod. Flujo: push a `main` construye la imagen una vez y la despliega a QA (`build` + `deploy-qa`). Publicar un Release `v*`
despliega esa misma imagen a prod (`deploy-prod`, con aprobación); prod nunca reconstruye. Cada deploy
(`deploy/scripts/deploy-env.sh`) migra con el job, despliega una revisión sin tráfico con tag `candidate`, corre el
smoke (`smoke.sh`) contra su URL y solo entonces mueve el 100% del tráfico.

Notas de seguridad y datos:

- **Un solo deployer.** `pomodoro-deployer` puede actuar como ambas SAs de runtime. La separación entre QA y prod no
  la da IAM sino tres piezas juntas: (1) la condición del Workload Identity Provider, que solo acepta tokens del
  repositorio con `ref == refs/heads/main` (build y `deploy-qa`) o `environment == prod` (`deploy-prod`), así que ningún
  otro workflow ni rama puede suplantar al deployer; (2) los revisores requeridos del environment `prod`; (3) su
  política de tags `v*`. Debilitar cualquiera de las tres abre un bypass a prod.
- **La branch `qa` de Neon se crea desde `prod`**, así que también contiene el rol y la base `pomodoro` de prod (con la
  contraseña de prod y una copia de los datos al momento del branch). La app en QA usa solo `pomodoro_qa`, pero quien
  tenga acceso a la consola de la branch `qa` ve esa copia.
- El estado de Terraform contiene las cadenas de conexión: tratar el bucket de estado como secreto.

## Prerequisitos

- `gcloud`, `terraform >= 1.9`, `jq`, Docker.
- Cuenta Neon con API key.
- Token de GitHub con admin del repositorio (`GITHUB_TOKEN` para el `apply`, que crea environments y variables).
- Los revisores requeridos en GitHub Environments de un repositorio privado necesitan un plan de pago (Team o
  Enterprise); sin él, `apply` falla al crear `prod` o la aprobación no se exige.
- Protección de `main`: debería exigir los checks de CI. Los workflows de CI filtran por paths, y un workflow filtrado no
  reporta en los PR que no tocan sus paths. Marcar como requeridos solo los checks que siempre corren, o aceptar que
  GitHub los muestre como pendientes ("expected"). Los de `deploy-ci` son `app-image`, `deploy-guards` y `terraform`.

## Bootstrap

Único paso manual fuera de Terraform: el bucket de estado.

```bash
export PROJECT_ID=...
gcloud auth application-default login
gcloud config set project "$PROJECT_ID"
gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com
gcloud storage buckets create "gs://${PROJECT_ID}-tfstate" --location=southamerica-east1 --uniform-bucket-level-access
gcloud storage buckets update "gs://${PROJECT_ID}-tfstate" --versioning
cd deploy/terraform && cp terraform.tfvars.example terraform.tfvars   # completar project_id y prod_reviewer_users
terraform init -backend-config="bucket=${PROJECT_ID}-tfstate"
```

Las dos APIs de `gcloud services enable` hacen falta antes del primer `apply` si no estaban habilitadas. En un proyecto
recién creado, el primer `apply` puede competir con la habilitación de APIs para la SA del deployer; volver a correr
`apply` lo resuelve.

## Primer apply

Se hace en pasos porque los servicios de Cloud Run necesitan una imagen existente (`:bootstrap`) en Artifact Registry.

```bash
export NEON_API_KEY=...  GITHUB_TOKEN=...       # solo en esta shell, nunca en archivos
terraform apply -target=google_project_service.apis -target=google_artifact_registry_repository.pomodoro
REPO=$(terraform output -raw image_repository)
gcloud auth configure-docker southamerica-east1-docker.pkg.dev
docker build -f ../Dockerfile -t "$REPO:bootstrap" ../.. && docker push "$REPO:bootstrap"
terraform plan -out=tfplan   # revisar
terraform apply tfplan
```

`bootstrap` arranca sin migraciones (el health no toca la base); el primer deploy migra. Después del primer deploy por
el pipeline, correr `terraform plan` una vez y confirmar que no muestra drift en los servicios de Cloud Run (el pipeline
cambia la imagen, el tráfico y los tags). Terraform ignora solo los campos de imagen y de cliente; el tráfico y los tags
no se ignoran, así que este `plan` confirma que no los revierte. Nunca aplicar un plan que cambie el tráfico: movería
el servicio fuera de la revisión desplegada por el pipeline.

## Primer deploy

El Terraform apply (y la imagen `bootstrap`) deben estar hechos **antes** de mergear esta rama: el merge a `main`
dispara `deploy.yml`, que necesita las variables de Actions, el repositorio de imágenes y los servicios ya creados.

Merge a `main`: el workflow `deploy` corre `build` y `deploy-qa`. La URL queda en el environment `qa` del run o en:

```bash
terraform output service_uris
```

## Verificación del rate limit en QA

Después del primer deploy, 5 logins fallidos contra un email de prueba, con un `X-Forwarded-For` distinto en cada uno.
El sexto debe dar 429:

```bash
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w '%{http_code}\n' -H "X-Forwarded-For: 198.51.100.$i" \
    -H 'Content-Type: application/json' -d '{"email":"ratelimit@example.com","password":"wrong"}' \
    "$QA_URL/api/auth/login"
done   # esperado: 401 x5, luego 429
```

Si no da 429: aplicar el plan B del spec (nginx reemplaza `X-Forwarded-For` en lugar de agregar) y repetir.

El loop anterior no detecta que la clave del limitador colapse a la dirección del front-end de Google que ve nginx
(todas las peticiones compartirían clave y también darían 429). Paso de observación: con `ratelimit@example.com` ya
bloqueado (6 intentos fallidos) desde una red, intentar un login con el mismo email desde otra red/IP (hotspot del
teléfono o Cloud Shell).

- Si **no** da 429 (da 401): la clave es la IP real del cliente. Correcto.
- Si **también** da 429: la clave colapsó a la dirección del proxy y el límite es efectivamente por email (un tercero
  podría bloquear a un usuario concreto). Fix, ya decidido y todavía no aplicado: definir
  `FORWARDED_ALLOW_IPS=169.254.0.0/16` para uvicorn en `deploy/entrypoint.sh` (o como env en Terraform) para que tome la
  IP de cliente que agrega Google. Luego repetir el loop con `X-Forwarded-For` falsos (debe seguir dando 429 al sexto) y
  la prueba de dos redes (la segunda red NO debe dar 429), y actualizar el guard
  `test_entrypoint_keeps_uvicorn_default_proxy_trust`.

Anotar abajo el comportamiento observado y la fecha.

Resultado observado: _pendiente (sin ejecutar todavía)_.

## Promoción a prod

1. Confirmar que el commit está en `main` y ya se desplegó y probó en QA.
2. Crear un Release de GitHub con tag `vX.Y.Z` sobre ese commit.
3. Aprobar el job `deploy-prod` (revisores del environment `prod`; solo acepta tags `v*`).

El job corre `deploy/scripts/verify-release.sh`: el SHA del release debe ser ancestro de `origin/main` y la imagen
`pomodoro-app:<sha>` debe existir en Artifact Registry; si no, aborta sin tocar nada. Luego aplica el mismo deploy que QA
(migración, candidate, smoke, tráfico).

## Rollback manual

```bash
gcloud run revisions list --service pomodoro-prod --region southamerica-east1
gcloud run services update-traffic pomodoro-prod --region southamerica-east1 --to-revisions <revision>=100
```

El próximo deploy vuelve a `--to-latest`. Las migraciones no se revierten: por eso deben ser compatibles hacia atrás
(expand/contract), ya que la revisión anterior sigue sirviendo sobre el esquema migrado.

## Reset de QA desde prod

QA usa rol y base propios (`pomodoro_qa`), así que se copian datos, no la branch:

```bash
read -rs PROD_DB_URL; read -rs QA_DB_URL   # URLs libpq: postgresql://...?sslmode=require (sin +psycopg)
pg_dump --format=custom --no-owner "$PROD_DB_URL" > prod.dump
pg_restore --clean --if-exists --no-owner --role=pomodoro_qa --dbname "$QA_DB_URL" prod.dump
rm prod.dump
```

Las URLs se leen de Secret Manager (`gcloud secrets versions access latest --secret pomodoro-prod-database-url`) y se
les quita `+psycopg`; no pegarlos en la shell history. Recordar que la branch `qa` de Neon conserva además una copia
antigua de prod (ver Arquitectura).

## Rotación de secretos y tokens

- **Contraseña de Neon**: resetear el rol en la consola de Neon, luego `terraform apply -refresh-only` para que el
  estado lea la nueva contraseña y `terraform apply` para regrabar el secreto `pomodoro-<env>-database-url`. Revisar el
  plan antes de aplicar.
- **Nueva versión de un secreto**: redeploy para que se tome (`version = "latest"` se resuelve al arrancar la instancia),
  forzando una revisión nueva:
  `gcloud run services update pomodoro-<env> --region southamerica-east1 --update-labels=rotated=$(date +%s)`.
  QA también se actualiza con el siguiente push a `main`; prod solo se redespliega con un release, así que ahí el
  comando es la vía normal.
- **`NEON_API_KEY` y `GITHUB_TOKEN`**: solo se usan en `apply`; revocarlos después si son de uso único.

## Subir max-instances

Hoy `max_instance_count = 1`. Subirlo requiere un rate limit compartido (el actual está en memoria y solo es correcto con
una instancia). Fuera de alcance hasta moverlo a un almacenamiento compartido; ver ADR-0004.

## Costos y arranque en frío

Cloud Run con mínimo 0 y Neon con autosuspend: costo en reposo mínimo, a cambio de arranque en frío (el smoke reintenta
para cubrirlo). Si molesta, `min_instance_count = 1` en prod, con costo.
