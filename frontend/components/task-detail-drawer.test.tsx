import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { apiClientModule, getMock } from "./api-client-mock";
import { TaskDetailDrawer } from "./task-detail-drawer";
import { IDLE_TIMER, makeTask, okResult } from "./task-fixtures";

vi.mock("@/lib/api-client", () => apiClientModule);

type HistoryBody = components["schemas"]["TaskHistoryResponse"];

const TASK = { ...makeTask("t1", "Escribir informe", ["g1"]) };
const TAGS = [{ id: "g1", name: "trabajo", color: "teal" }];
const EMPTY_HISTORY: HistoryBody = {
  completed_count: 0,
  dedicated_seconds: 0,
  first_day: null,
  last_day: null,
  active_days: 0,
  days: [],
};

function isoToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

interface Scenario {
  history?: HistoryBody;
  historyStatus?: number;
  archived?: (typeof TASK)[];
  timer?: unknown;
}

function setup({
  history = EMPTY_HISTORY,
  historyStatus = 200,
  archived = [],
  timer,
}: Scenario = {}) {
  getMock.mockImplementation((path: string) => {
    if (path === "/api/v1/tasks/{task_id}/history") {
      if (historyStatus !== 200) {
        return Promise.resolve({ data: undefined, error: {}, response: { status: historyStatus } });
      }
      return okResult(history);
    }
    if (path === "/api/v1/tasks") {
      return okResult({ tasks: archived.length ? [] : [TASK], active_count: 1, archived_count: 0 });
    }
    if (path === "/api/v1/tasks/archived") {
      return okResult({ tasks: archived, active_count: 0, archived_count: archived.length });
    }
    if (path === "/api/v1/tags") {
      return okResult({ tags: TAGS });
    }
    if (path === "/api/v1/timer") {
      return okResult(timer ?? IDLE_TIMER);
    }
    return okResult({});
  });
  const onClose = vi.fn();
  const view = render(<TaskDetailDrawer taskId="t1" onClose={onClose} />);
  return { onClose, ...view };
}

describe("TaskDetailDrawer", () => {
  beforeEach(() => getMock.mockReset());
  afterEach(() => vi.restoreAllMocks());

  it("shows text, Active status, colored Tags, totals, range and month breakdown", async () => {
    const today = isoToday();
    setup({
      history: {
        completed_count: 3,
        dedicated_seconds: 4500,
        first_day: "2026-09-02",
        last_day: today,
        active_days: 2,
        days: [
          { day: today, completed_count: 2, dedicated_seconds: 3000 },
          { day: "2026-09-02", completed_count: 1, dedicated_seconds: 1500 },
        ],
      },
    });
    const dialog = await screen.findByRole("dialog", { name: "Detalle de Escribir informe" });
    expect(await within(dialog).findByText("Activa")).toBeTruthy();
    expect(within(dialog).getByText("trabajo")).toBeTruthy();
    expect(within(dialog).getByTestId("drawer-tag-dot").className).toContain("bg-tag-teal");
    expect(await within(dialog).findByText("3 Pomodoros · 1h 15m")).toBeTruthy();
    expect(within(dialog).getByText(/2\/9\/2026 – \d+\/\d+\/\d{4} · 2 días/)).toBeTruthy();
    expect(within(dialog).getByText("Hoy")).toBeTruthy();
    expect(within(dialog).getByText("2 pomodoros · 50m")).toBeTruthy();
    expect(within(dialog).getByText("2/9/2026")).toBeTruthy();
    expect(within(dialog).getByText("1 pomodoros · 25m")).toBeTruthy();
    expect(within(dialog).getByText("1 · 25m")).toBeTruthy();
  });

  it("shows the empty state for a Task that never received time", async () => {
    setup();
    expect(await screen.findByText("Todavía sin Pomodoros")).toBeTruthy();
  });

  it("shows Archivada for an archived Task", async () => {
    setup({ archived: [{ ...TASK, archived_at: "2026-02-01T00:00:00Z" }] });
    expect(await screen.findByText("Archivada")).toBeTruthy();
  });

  it("shows En curso when the Timer holds the Task", async () => {
    setup({
      timer: { ...IDLE_TIMER, phase: "PomodoroRunning", task: { id: "t1", text: TASK.text } },
    });
    expect(await screen.findByText("En curso")).toBeTruthy();
  });

  it("shows a generic error when the history cannot be loaded", async () => {
    setup({ historyStatus: 404 });
    expect(await screen.findByText("No se pudo cargar el detalle.")).toBeTruthy();
  });

  it("closes with the ✕ button, Esc, and a click outside", async () => {
    const user = userEvent.setup();
    const { onClose } = setup();
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: "Cerrar detalle" }));
    await user.keyboard("{Escape}");
    await user.click(screen.getByTestId("drawer-backdrop"));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(3));
  });

  it("moves focus into the dialog on open", async () => {
    setup();
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
  });
});
