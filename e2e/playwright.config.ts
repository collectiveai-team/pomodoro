import { defineConfig } from "@playwright/test";

/**
 * Smoke suite against the real docker-compose stack (T31) -- never a mocked
 * backend. E2E_BASE_URL points at the frontend's published port; the CI job
 * (.github/workflows/e2e.yml) is responsible for bringing the stack up,
 * waiting for health, and tearing it down, so this config never starts a
 * server itself.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
});
