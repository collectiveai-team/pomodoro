# Conventions

Repository rules for every agent and human working in this repo. Roles read this
file instead of inferring the project from nearby files.

## Status

Stack: **Python 3.14 with uv** today. The agreed target (spec in issue #12,
ADR-0001/0002/0003) is a web app in a monorepo: `backend/` (FastAPI, SQLModel +
Alembic, SQLite locally and PostgreSQL in production) and `frontend/` (Next.js App
Router, TypeScript, pnpm, Tailwind, Biome). Tooling, gates, and a root `pomodoro`
package placeholder exist; the domain model does not yet. Sections marked **OPEN** below
await the product objective. Do not invent them; ask.

## Engineering standards (botica) — read before writing code

House standards come from botica (`collectiveai-team/botica`) and are installed in this repo.
Prefer them over training-default patterns:

- **Index:** `AGENTS.md` → "Engineering Standards" lists every CES rule with its slug. Before
  writing code a rule touches, open its detail file in `.agents/rules/<slug>.md` and copy the
  matching drop-in from `.agents/snippets/` (`api-schemas.py`, `settings.py`,
  `core/logger.py`, `no-dict-boundary.py`, `tests/in_memory_repository.py`).
- **Stack rules:** load the `engineering-rules` skill and read `rules/_sections.md`, then only
  the rules the work touches. For this repo that is at least section 8 FastAPI
  (`api-structure`, `api-pydantic-settings`, `api-sqlmodel-alembic`, `api-schemas`,
  `api-auth`), section 12 Next.js (`fe-*`), and the testing and architecture sections.
- **Workflow skills:** `tdd` for every behaviour change, `codebase-design` /
  `domain-modeling` when shaping modules or the domain, `test-smell-review` after writing
  tests, `engineering-pr-review` before opening or updating a PR.
- **Precedence:** issue #12's spec and the ADRs in `docs/adr/` win over a generic house rule
  when they conflict (e.g. migrations run as a separate step, never at app startup, even though
  `api-sqlmodel-alembic` says otherwise). Record any such deviation in the ticket or PR.

API boundary checklist (CES-4, CES-17, CES-76, CES-79):

- Versioned inbound package: `api/<v>/routers/` and `api/<v>/schemas/{requests,responses}/`;
  routers stay thin and delegate to use cases; no schema classes inside router modules.
- Every request/response model sets `model_config = ConfigDict(extra="forbid")` and declares
  field constraints with `Field(...)` instead of re-validating by hand.
- Settings only through the `BaseSettings` module and `get_settings()`; no `os.environ`
  elsewhere.
- Domain errors map to HTTP in one place (exception handlers registered by the app factory),
  with one error response shape; routes declare their error `responses=`.
- Dependencies are real FastAPI providers wired in the app factory, not stubs that raise.

## Commit policy

- **Conventional Commits** are mandatory on the subject line:
  `type(scope): description`, where type is one of `feat fix docs style refactor
  perf test build ci chore revert`. Enforced locally by the `agents-conventional-commits`
  commit-msg hook and in CI by `.github/workflows/conventional-commits.yml`.
  `Merge `/`Revert `/`fixup! ` subjects are exempt.
- **No AI co-authorship or attribution trailers.** No `Co-authored-by:` naming an
  AI tool, no `Generated with:`, no `Assisted-by:`. Commit metadata stays
  human-accountable. Enforced by the `no-ai-coauthorship` commit-msg hook, with
  `.github/workflows/commit-policy.yml` as the source of truth (a local hook can
  be bypassed with `--no-verify`; CI cannot).
- Commit only what the current objective touches. Never commit unrelated staged work.

## Secrets

- Secrets live outside the repo. `.env.schema` is committed and describes the
  shape; `.env` and friends are gitignored.
- **Never read `.env` directly** — no `cat`, no `Read`. Use `varlock load`
  (`npm exec -- varlock load --agent` prints JSON with sensitive values redacted,
  safe for logs and transcripts).
- `opencode.jsonc` and `.claude/settings.json` carry deny-lists for `.env*`,
  `*.pem`, `*.key`, `*credentials*`, and `varlock.config`. Codex has no
  repo-local deny-list, so the rules in this file plus the leak-scan hook are its
  only guardrails.
- The `betterleaks` pre-commit hook scans staged changes. A hook failure is a
  real finding until proven otherwise; never `--no-verify` past it.

## Local gates (prek)

`prek.toml` runs on commit: merge-conflict markers, files over 750 KB,
TOML/YAML validity, end-of-file and trailing-whitespace fixes, `betterleaks`
secret scanning, `jscpd` copy-paste duplication (fails above 1%), and `hadolint`
when a `Dockerfile` exists. Hooks are wired via
`prek install --hook-type pre-commit --hook-type commit-msg`.

The two local commit-msg hooks invoke **`python3`**, not `python`: this
environment ships no unversioned `python` binary. Keep it that way.

`jscpd` failing means extract a shared helper — do not raise the threshold.

## CI

Workflows live in `.github/workflows/`. House style: every `uses:` pinned to a
tag, never a branch (`astral-sh/setup-uv` must be pinned to an exact version such
as `@v8.3.2`, since it stopped publishing major tags at v8.0.0), plus a
`concurrency` group and least-privilege `permissions` on every workflow.
`zizmor` statically analyses the workflows themselves and must stay green.

## Generated and derived files — never hand-edit

- `skills-lock.json` is the tracked skills manifest, owned by the `skills` CLI.
  Add skills with `npx skills add <source> --agent opencode --yes --skill <name>`.
  Re-serialising the file drops `ref`, `skillPath`, and `computedHash`.
- `.agents/skills/` is *derived* from that manifest and gitignored. `.claude/skills`
  is a symlink to it; `CLAUDE.md` is a symlink to `AGENTS.md`.
- `team.json` and `.orquestalite/` are local orq-lite runtime configuration and
  state, gitignored by design. Project-owned flows under `flows/` may be tracked.

## Workspace layout

- `.scratch/` — temporary plans, issue drafts, disposable notes.
- `.tmp/` — generated local artifacts, never committed.
- `.worktrees/` — local git worktrees.
- `.journals/` — private session journals.

Run expensive commands (heavy builds, full suites, data jobs) under `systemd-run`
with `MemoryMax`, `MemorySwapMax=0`, and `CPUQuota` caps, logging wall time and
peak memory via `/usr/bin/time -v` under `.tmp/logs/`. See `AGENTS.md`. A step
that is consistently too expensive is a code smell to flag, not a limit to raise.

## Issues and domain docs

- Issues are **GitHub issues** in `collectiveai-team/pomodoro`, driven by the `gh`
  CLI. See `docs/agents/issue-tracker.md`.
- Triage vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`,
  `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.
- Single-context domain docs: a root `CONTEXT.md` plus `docs/adr/`, both created
  lazily when terms or decisions actually resolve. Use the glossary's vocabulary
  in issue titles, test names, and proposals; surface ADR contradictions
  explicitly rather than silently overriding them. See `docs/agents/domain.md`.

## Code style

Configured centrally in `pyproject.toml`; do not re-litigate per file.

- **ruff** is the linter and formatter: line length 100, double quotes, isort
  import ordering, google-convention docstrings, mccabe complexity ≤ 10.
  Relative imports are banned outright — use absolute package imports so modules
  can move.
- **pyrefly** type-checks against the same `pyproject.toml`.
- **complexipy** caps *cognitive* complexity at 15 per function, which penalises
  nesting and control-flow breaks that ruff's cyclomatic check forgives. Hoist a
  nested helper to module level rather than raising the ceiling.
- **file-size-guard** warns at 400 lines and fails at 700.
- **no-utils**: no `utils.py`/`helpers.py`/`aux.py`/`misc.py`/`common.py`. Name a
  module for what it holds.
- **repo-shape**: no notebooks, `resources/`, `reports/`, or `data/` inside
  `pomodoro`.
- **deptry** keeps declared dependencies and the real import graph in sync — no
  unused, missing, or dev-vs-prod misplaced dependencies.
- **ast-grep** (`ast-grep/rules/`) rejects dict-shaped returns from boundary
  functions: prefer a `@dataclass`, or a pydantic model where validation matters.

Legitimate exceptions belong in the central config, not in per-file noqa drifts.
`tests/**` already waives `S101` (assert), `INP001`, and `S603`/`S607` (tests
shell out to `git` and `orq-lite` by name).

## Architecture boundaries

The import package is `pomodoro` at the repository root (flat layout), packaged
as a wheel by hatchling.

The house layer direction is `entrypoints -> api -> database|impl -> core`: a
higher layer may import lower ones, never the reverse, and `api` is the only
inbound HTTP boundary. `pyproject.toml` carries a commented `[tool.importlinter]`
skeleton — uncomment and enforce it once the package actually has layers.

Agreed layout for the backend (ADR-0001, to be enforced once the packages exist):
`entrypoints` (FastAPI app factory, settings, dependency wiring) -> `api` (versioned
`api/<v>/` with `routers/` and `schemas/{requests,responses}/` per CES-17, plus use cases) ->
`database` (SQLModel tables, repositories,
Alembic) -> `core` (entities, rules, Timer state machine, repository Protocols; no
framework imports). The package moves under `backend/` when implementation starts.

## Test strategy

**pytest**, tests under `tests/`, `asyncio_mode = "auto"`. Markers: `unit` (fast,
isolated, no external deps), `integration` (external services or multi-component),
`e2e` (smoke).

- **pytest-randomly** randomises order every run with a reproducible seed. An
  order-dependent or state-leaking test is therefore a bug, not bad luck.
- **pytest-timeout** bounds hangs.
- The deterministic suite must touch **no network and no real database**, and must
  not depend on local `.env` values, service credentials, or execution order.
- A check that depends on gitignored local state (such as `team.json`) must
  `pytest.skip` when it is absent, so a fresh clone stays green.

The deterministic gates in `team.json`, both proven green from a fresh clone and
each proven able to go red:

```json
"lint_argv": ["uv", "run", "ruff", "check", "."],
"test_argv": ["uv", "run", "pytest", "-q"]
```

They are argv arrays run directly from the repository root with shell access
disabled — never pipelines, redirects, `cd`, or environment assignments. **A
failing gate aborts the entire orq-lite flow**, and later roles treat green as
evidence, so never weaken a gate to make a run pass: fix the project.

## Compatibility promises

- **Python 3.14** is the floor (`requires-python = ">=3.14"`, pinned for the
  toolchain by `.python-version`).
- The version is derived from git tags (`vX.Y.Z`) by hatch-vcs; untagged builds
  get a `0.1.devN+g<sha>` development version. Do not hand-write a version.
- Nothing is published to any index and there is no release workflow, so there is
  no external API stability promise yet.

**OPEN** once anything is consumed outside this repo: the public surface, its
stability guarantee, and a deprecation policy.

## Deployment (Docker)

- `backend/Dockerfile` (FastAPI under uvicorn) and `frontend/Dockerfile` (Next.js standalone) are
  built from the repository root context; both are linted by `hadolint` (CES-114).
- `docker-compose.yml` runs PostgreSQL + backend + frontend as a production-like local stack.
  **Binding deviation from the generic `api-sqlmodel-alembic` rule (ADR-0002, spec):** Alembic
  migrations run as an explicit one-shot step (`docker compose run --rm migrate`, also a
  `service_completed_successfully` dependency of `backend`), never at app startup. Record this
  in the PR.
- Docker-less local development is unchanged: SQLite under `backend/.tmp/`, no external services.
- Smoke check: `backend/scripts/smoke_compose.sh` builds, migrates, brings the stack up, confirms
  `/api/health` through the frontend (`FRONTEND_PORT`, default 3000), then tears it down.

## Browser and API verification

- **Dev server (frontend only, needs a backend on `BACKEND_INTERNAL_URL`):** `cd frontend && pnpm dev`,
  base URL `http://localhost:3000`. **Production-like stack:** `docker compose up -d --wait` after
  `docker compose run --rm migrate`, base URL `http://localhost:${FRONTEND_PORT:-3000}`; set
  `FRONTEND_PORT` when 3000 is busy.
- **E2E smoke (Playwright, `e2e/`):** register, create a Task, start/pause a Pomodoro, reload
  (same Timer state), logout. It is its own pnpm package and CI workflow (`.github/workflows/e2e.yml`),
  never part of `uv run pytest -q`. Run it with the shared compose lifecycle (build, explicit
  migrate, up, health check, command, teardown on any exit):
  `cd e2e && pnpm install && pnpm exec playwright install chromium && cd .. &&
  FRONTEND_PORT=3111 backend/scripts/smoke_compose.sh pnpm --dir e2e exec playwright test`.
  Set `PLAYWRIGHT_CHANNEL=chrome` where Playwright has no bundled browser for the OS.
- `agent-browser` (`npm i -g agent-browser && agent-browser install`) lets the `visual_verifier`
  role drive a real browser instead of falling back to playwright/curl.
