import { defineConfig } from "@playwright/test";

// Runs against the docker compose stack, never a dev server: backend/scripts/smoke_compose.sh
// exports BASE_URL (honouring FRONTEND_PORT) and tears the stack down afterwards.
export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    // Set PLAYWRIGHT_CHANNEL=chrome where Playwright has no bundled browser for the OS.
    channel: process.env.PLAYWRIGHT_CHANNEL,
    trace: "retain-on-failure",
  },
});
