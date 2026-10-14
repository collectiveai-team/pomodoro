import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { broadcastTimerChanged } from "@/lib/timer-sync";
import { IDLE_TIMER, makeTask } from "./task-fixtures";
import { TasksPanel } from "./tasks-panel";

type TagResponseBody = components["schemas"]["TagResponse"];

const getMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: { GET: (...args: unknown[]) => getMock(...args) },
}));

function result(data: unknown) {
  return Promise.resolve({ data, error: undefined, response: { status: 200 } as Response });
}

function setup(dayTasks: () => unknown[], tags: TagResponseBody[] = []) {
  const tasks = [
    makeTask(
      "a",
      "Write report",
      tags.map((tag) => tag.id),
    ),
    makeTask("b", "Idle one"),
  ];
  getMock.mockImplementation((path: string) => {
    if (path === "/api/v1/tags") return result({ tags });
    if (path === "/api/v1/timer") return result({ ...IDLE_TIMER });
    if (path === "/api/v1/history/day") {
      return result({ day: "2026-10-14", completed_count: 0, tasks: dayTasks() });
    }
    return result({ tasks, active_count: 2, archived_count: 0 });
  });
}

function rowOf(text: string): HTMLElement {
  const row = screen.getByText(text).closest("li");
  if (!row) throw new Error(`no row for ${text}`);
  return row;
}

beforeEach(() => getMock.mockReset());

describe("TasksPanel — row layout and today's stats", () => {
  it("shows count and time for a Task with Pomodoros today, nothing for others", async () => {
    setup(() => [
      { task_id: "a", text: "Write report", completed_count: 3, dedicated_seconds: 5400 },
    ]);
    render(<TasksPanel />);

    expect(
      await within(
        (await screen.findByText("Write report")).closest("li") as HTMLElement,
      ).findByText("3 hoy · 1h 30m"),
    ).toBeVisible();
    expect(within(rowOf("Idle one")).queryByText(/hoy/)).toBeNull();
  });

  it("refreshes the stats when the Timer changes", async () => {
    let seconds = 1500;
    setup(() => [
      { task_id: "a", text: "Write report", completed_count: 1, dedicated_seconds: seconds },
    ]);
    render(<TasksPanel />);
    await screen.findByText("1 hoy · 25m");

    seconds = 3000;
    broadcastTimerChanged();
    expect(await screen.findByText("1 hoy · 50m")).toBeVisible();
  });

  it("renders colored Tag pills and the ▶ ⓘ 🏷 ⋯ controls, without the old chip editor", async () => {
    setup(() => [], [{ id: "t1", name: "Work", color: "rose" }]);
    render(<TasksPanel />);

    const row = (await screen.findByText("Write report")).closest("li") as HTMLElement;
    await waitFor(() => expect(within(row).getByText("Work").className).toContain("text-tag-rose"));
    for (const name of [
      "Iniciar Pomodoro en Write report",
      "Detalle de Write report",
      "Etiquetas de Write report",
      "Acciones de Write report",
    ]) {
      expect(within(row).getByRole("button", { name })).toBeVisible();
    }
    expect(within(row).queryByRole("button", { name: /Quitar etiqueta/ })).toBeNull();
    expect(within(row).queryByRole("combobox")).toBeNull();
  });
});
