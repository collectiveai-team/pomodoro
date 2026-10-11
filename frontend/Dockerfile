# Frontend image: Next.js standalone output (ADR-0001). `/api/*` is rewritten to the backend;
# Next bakes rewrites into the build, so BACKEND_INTERNAL_URL is a build argument.
FROM node:24-slim AS build

ENV PNPM_HOME=/pnpm \
    PATH="/pnpm:$PATH" \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
RUN pnpm run build

FROM node:24-slim

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/edge/stamp-client-address.cjs ./edge/stamp-client-address.cjs

USER 1000
EXPOSE 3000
# The preload stamps X-Forwarded-For with the socket address before Next sees the request, so the
# backend's login rate limit keys on an IP the browser cannot choose (edge/stamp-client-address.cjs).
CMD ["node", "--require", "./edge/stamp-client-address.cjs", "server.js"]
