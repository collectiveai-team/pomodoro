# Web app: Next.js frontend + FastAPI backend, same origin, in a monorepo

Pomodoro Collective is a multi-user web app with registration and login. We chose a Next.js (App Router, TypeScript) frontend and a FastAPI backend, kept in this repo as `frontend/` and `backend/` so domain docs, ADRs and issues stay in one place. FastAPI was picked over Django because it fits the house strict layers (`entrypoints -> api -> database -> core`) without importing Django's conventions, and its OpenAPI output gives a typed contract from which the frontend's TypeScript client is generated (checked for drift in CI). The browser only talks to the Next.js origin; `/api/*` is rewritten to FastAPI, so the auth cookie is first-party with no CORS or `SameSite=None`. Next.js is not a BFF: it renders the UI and holds no domain logic.

Authentication is owned entirely by FastAPI: email + password (Argon2 via `pwdlib`), an opaque server-side session stored in the database and sent as an `HttpOnly; Secure; SameSite=Lax` cookie, revocable on logout. JWTs and Auth.js were rejected because they split auth across two runtimes or make revocation harder; `fastapi-users` was rejected as being in maintenance mode.

## Considered Options

- **Django + DRF/Ninja**: built-in auth, ORM and migrations, at the cost of heavier conventions that clash with the house layering.
- **Separate origins (`app.` / `api.`)**: requires CORS and cross-site cookies for no benefit.
- **Next.js server actions as a BFF**: duplicates the boundary and pulls logic into the frontend.

## Consequences

- Backend layer roles: `entrypoints` is the FastAPI app factory, settings and dependency wiring; `api` holds per-area routers, Pydantic request/response schemas and use cases (it is the only inbound HTTP boundary); `database` holds persistence; `core` keeps the domain rules with no framework imports. The `Clock` abstraction only answers "what time is it now" — the screen-refresh tick lives in the browser.
- Deployment is two Docker images (frontend, backend) plus managed PostgreSQL; the concrete host is decided separately.
