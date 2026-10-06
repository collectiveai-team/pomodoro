# syntax=docker/dockerfile:1
#
# Production image for the Next.js frontend, built in standalone output mode
# (next.config.ts: output: "standalone") so the runtime stage only needs the
# traced server output, not the full node_modules/.next build tree.
#
# Build context is this directory (frontend/ is a self-contained pnpm project
# with its own lockfile):
#
#   docker build -f frontend/Dockerfile -t pomodoro-frontend frontend
#
# /api/* is proxied to the backend by proxy.ts, which reads BACKEND_ORIGIN
# from the environment on every request -- so the same image can point at
# different backend hosts in different environments without a rebuild. See
# proxy.ts for why this isn't done via next.config.ts
# rewrites, which `next build` would otherwise freeze into a fixed
# destination in .next/routes-manifest.json at build time.

ARG NODE_VERSION=24-slim

FROM node:${NODE_VERSION} AS base
RUN corepack enable
WORKDIR /app

# ---- deps: install dependencies from the lockfile only ----
FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# ---- builder: add source, produce the standalone build ----
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm run build

# ---- runtime: copy only the traced standalone output, drop root ----
FROM node:${NODE_VERSION} AS runtime
# uid/gid 1001, not 1000: the base node image already ships a uid/gid 1000
# "node" user, and groupadd/useradd would collide with it.
RUN groupadd --system --gid 1001 nextjs \
    && useradd --system --uid 1001 --gid nextjs --home-dir /app nextjs
WORKDIR /app
RUN chown nextjs:nextjs /app
COPY --from=builder --chown=nextjs:nextjs /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

USER 1001:1001
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]

CMD ["node", "server.js"]
