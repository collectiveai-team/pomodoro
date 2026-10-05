#!/usr/bin/env -S pnpm exec tsx
/**
 * Manual smoke check for the generated API client (T19): a real, typed call
 * against a locally running backend, proving the generated types + client
 * wrapper compile and actually work end to end (not just in isolation).
 *
 * Usage: start the backend (`uv run pomodoro-api`), then from `frontend/`:
 *   pnpm exec tsx scripts/sample-api-call.ts
 */
import { apiClient } from "../src/api/client";

async function main(): Promise<void> {
  const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
  const { response } = await apiClient.GET("/api/auth/me", {
    baseUrl: backendOrigin,
  });
  console.log(`GET /api/auth/me -> ${response.status}`);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
