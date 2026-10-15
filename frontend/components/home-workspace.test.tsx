import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClientModule, getMock } from "./api-client-mock";
import { HomeWorkspace } from "./home-workspace";
import { IDLE_TIMER, makeTask, okResult } from "./task-fixtures";

vi.mock("@/lib/api-client", () => apiClientModule);
vi.mock("@/lib/alarm", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/alarm")>()),
  unlockAlarm: vi.fn(),
}));

const EMPTY_HISTORY = {
  completed_count: 0,
  dedicated_seconds: 0,
  first_day: null,
  last_day: null,
  active_days: 0,
  days: [],
};

function routeApi(timer: unknown = IDLE_TIMER) {
  const active = makeTask("a1", "Tarea activa");
  const archived = { ...makeTask("r1", "Tarea vieja"), archived_at: "2026-02-01T00:00:00Z" };
  getMock.mockImplementation((path: string) => {
    switch (path) {
      case "/api/v1/tasks":
        return okResult({ tasks: [active], active_count: 1, archived_count: 1 });
      case "/api/v1/tasks/archived":
        return okResult({ tasks: [archived], active_count: 1, archived_count: 1 });
      case "/api/v1/tasks/{task_id}/history":
        return okResult(EMPTY_HISTORY);
      case "/api/v1/timer":
        return okResult(timer);
      case "/api/v1/tags":
        return okResult({ tags: [] });
      case "/api/v1/settings":
        return okResult({});
      default:
        return okResult({ tasks: [], days: [] });
    }
  });
}

describe("HomeWorkspace task detail", () => {
  beforeEach(() => getMock.mockReset());

  it("opens the detail drawer from an Active row's ⓘ", async () => {
    routeApi();
    const user = userEvent.setup();
    render(<HomeWorkspace />);
    await user.click(await screen.findByRole("button", { name: "Detalle de Tarea activa" }));
    expect(await screen.findByRole("dialog", { name: "Detalle de Tarea activa" })).toBeTruthy();
  });

  it("opens the detail drawer from an Archived row's ⓘ", async () => {
    routeApi();
    const user = userEvent.setup();
    render(<HomeWorkspace />);
    await user.click(await screen.findByRole("tab", { name: /Archivadas/ }));
    await user.click(await screen.findByRole("button", { name: "Detalle de Tarea vieja" }));
    const dialog = await screen.findByRole("dialog", { name: "Detalle de Tarea vieja" });
    expect(await within(dialog).findByText("Archivada")).toBeTruthy();
  });

  it("opens the detail drawer from the Timer's Task card ⓘ and closes it", async () => {
    routeApi({
      ...IDLE_TIMER,
      phase: "PomodoroRunning",
      task: { id: "a1", text: "Tarea activa" },
      remaining_seconds: 1500,
    });
    const user = userEvent.setup();
    render(<HomeWorkspace />);
    await user.click(await screen.findByRole("button", { name: "Ver detalle de Tarea activa" }));
    const dialog = await screen.findByRole("dialog", { name: "Detalle de Tarea activa" });
    expect(await within(dialog).findByText("En curso")).toBeTruthy();
    await user.click(within(dialog).getByRole("button", { name: "Cerrar detalle" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
