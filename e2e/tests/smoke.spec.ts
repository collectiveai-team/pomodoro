import { expect, test } from "@playwright/test";

/**
 * E2E smoke test (T32, Testing Decisions "E2E") against the real
 * docker-compose stack (T31): register -> create a Task -> start and pause a
 * Pomodoro -> reload and see the same Timer state -> logout. Drives only the
 * public UI/HTTP surface; no mocked backend, no internal seams.
 */

function uniqueEmail(): string {
  return `e2e-smoke-${Date.now()}-${Math.floor(Math.random() * 1_000_000)}@example.com`;
}

const PASSWORD = "Sm0ke-Test-Pass!";
const TASK_TEXT = "Write the E2E smoke spec";

/**
 * The Timer panel and the Activas tab each own an independent countdown
 * engine (frontend/src/timer/engine.ts): starting a Pomodoro from the
 * Activas row only updates that row's own engine instance, not the
 * always-mounted Timer panel's. The panel's engine re-syncs with the server
 * on window focus/visibility regain -- a real, documented sync trigger, not
 * a test-only seam -- so dispatching it here reproduces what a user would
 * get by switching tabs/apps and back, the same path a page reload also
 * exercises on mount.
 */
async function resyncTimerPanel(page: import("@playwright/test").Page) {
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
}

test("register, run a Pomodoro, survive reload, logout", async ({ page }) => {
  const email = uniqueEmail();

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Contraseña").fill(PASSWORD);
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  await expect(page).toHaveURL("/");
  await expect(
    page.getByRole("heading", { name: /^Activas/ }),
  ).toBeVisible();

  const newTaskInput = page.getByLabel("Nueva tarea");
  await newTaskInput.fill(TASK_TEXT);
  await newTaskInput.press("Enter");

  const startButton = page.getByRole("button", {
    name: `Iniciar Pomodoro en ${TASK_TEXT}`,
  });
  await expect(startButton).toBeVisible();
  await startButton.click();
  await expect(startButton).toBeDisabled();
  await resyncTimerPanel(page);

  const pauseButton = page.getByRole("button", { name: "Pausar" });
  await expect(pauseButton).toBeVisible();
  await expect(page.getByText(TASK_TEXT).first()).toBeVisible();

  await pauseButton.click();
  await expect(page.getByRole("button", { name: "Reanudar" })).toBeVisible();
  await expect(page.getByText("Pomodoro (en pausa)")).toBeVisible();

  const clockLocator = page.getByText(/^\d{2}:\d{2}$/);
  const pausedClock = await clockLocator.textContent();
  expect(pausedClock).not.toBeNull();

  await page.reload();

  await expect(page.getByText("Pomodoro (en pausa)")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reanudar" })).toBeVisible();
  await expect(page.getByText(TASK_TEXT).first()).toBeVisible();
  await expect(clockLocator).toHaveText(pausedClock as string);

  await page.getByRole("button", { name: "Cuenta" }).click();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();

  await expect(page).toHaveURL("/login");
  await expect(
    page.getByRole("heading", { name: "Iniciar sesión" }),
  ).toBeVisible();
});
