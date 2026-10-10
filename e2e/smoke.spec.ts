import { expect, test } from "@playwright/test";

// Self-contained: registers a unique account, so it never depends on test order or prior data.
test("register, create a Task, start and pause a Pomodoro, reload, logout", async ({ page }) => {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
  const taskText = "E2E smoke task";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.getByLabel("Nueva tarea").fill(taskText);
  await page.getByLabel("Nueva tarea").press("Enter");
  await expect(page.getByText(taskText)).toBeVisible();

  await page.getByRole("button", { name: `Iniciar Pomodoro en ${taskText}` }).click();
  await page.getByRole("button", { name: "Pausar" }).click();
  await expect(page.getByRole("button", { name: "Reanudar" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("button", { name: "Reanudar" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pausar" })).toHaveCount(0);

  await page.getByRole("button", { name: "Cuenta" }).click();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
});
