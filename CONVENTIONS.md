# Conventions

Repository rules for every agent and human working in this repo. Roles read this
file instead of inferring the project from nearby files.

## Status: pre-stack

This repository currently contains **only tooling** — no application code, no
language runtime, no package manager, no tests. Sections marked **OPEN** below
cannot be filled until the stack is chosen. Do not invent them; ask.

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

## Code style — OPEN

Depends on the stack. Fill in: formatter and linter with their exact
configuration, import ordering, naming, typing strictness, error-handling and
logging conventions.

## Architecture boundaries — OPEN

Depends on the stack. Fill in: module/package layout, dependency direction, what
may import what, where side effects and I/O are allowed.

## Test strategy — OPEN

Depends on the stack. Fill in: framework, unit/integration split, fixture and
factory rules, what may touch the network or a real database (the deterministic
suite must touch neither), coverage expectations.

The deterministic gates `lint_argv` and `test_argv` in `team.json` are currently
**empty**, so every gated orq-lite flow refuses to start. They must be argv
arrays runnable from the repository root — no pipelines, redirects, `cd`, or env
assignments — proven green from a fresh clone **and** proven able to go red.

## Compatibility promises — OPEN

Depends on the stack and whether anything is published. Fill in: supported
runtime versions, public API surface and its stability, deprecation policy,
migration expectations.

## Browser and API verification — OPEN

No UI surface exists yet. When one lands: record the dev-server start command and
base URL here, encode stable checks as Playwright (or equivalent) tests run by
`test_argv`, and install `agent-browser` (`npm i -g agent-browser && agent-browser install`)
so the `visual_verifier` role can drive a real browser instead of falling back to
playwright/curl.
