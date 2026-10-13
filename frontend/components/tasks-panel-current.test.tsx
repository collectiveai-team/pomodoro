import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { broadcastTimerChanged } from "@/lib/timer-sync";
import { TasksPanel } from "./tasks-panel";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TimerResponseBody = components["schemas"]["TimerResponse"];

const getMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: { GET: (...args: unknown[]) => getMock(...args) },
}));

function ok(): Response {
  return { status: 200 } as Response;
}

function makeTask(id: string, text: string): TaskResponseBody {
  return {
    id,
    text,
    position: 0,
    tag_ids: [],
    created_at: "2026-01-01T00:00:00Z",
    archived_at: null,
    deletable: true,
  };
}

function makeTimer(
  phase: TimerResponseBody["phase"],
  task: TaskResponseBody | null,
): TimerResponseBody {
  return {
    phase,
    task: task ? { id: task.id, text: task.text } : null,
    break_kind: null,
    phase_started_at: null,
    accumulated_active_seconds: 0,
    running_since: null,
    server_now: "2026-01-01T00:00:00Z",
    remaining_seconds: null,
    pomodoros_completed_today: 0,
    pomodoros_until_long_break: 4,
  };
}

const taskA = makeTask("a", "Task A");
const taskB = makeTask("b", "Task B");

function mockApi(timer: () => TimerResponseBody) {
  getMock.mockImplementation((path: string) => {
    const tasks = { tasks: [taskA, taskB], active_count: 2, archived_count: 0 };
    const data =
      path === "/api/v1/tags"
        ? { tags: [] }
        : path === "/api/v1/timer"
          ? timer()
          : path.startsWith("/api/v1/tasks")
            ? tasks
            : undefined;
    return Promise.resolve({ data, error: undefined, response: ok() });
  });
}

function rowOf(text: string): HTMLElement {
  const row = screen.getByText(text).closest("li");
  if (!row) {
    throw new Error(`no row for ${text}`);
  }
  return row;
}

beforeEach(() => {
  getMock.mockReset();
});
afterEach(() => vi.restoreAllMocks());

describe("TasksPanel — row held by the Timer", () => {
  it("marks only the Timer's Task row while the Timer is not Idle", async () => {
    mockApi(() => makeTimer("PomodoroRunning", taskA));
    render(<TasksPanel />);

    await waitFor(() => expect(rowOf("Task A")).toHaveAttribute("aria-current", "true"));
    expect(rowOf("Task A").className).toContain("ring-accent");
    expect(rowOf("Task A").className).toContain("dark:bg-accent/20");
    expect(rowOf("Task B")).not.toHaveAttribute("aria-current");
    expect(rowOf("Task B").className).not.toContain("ring-accent");
  });

  it("drops the highlight when the Timer returns to Idle and moves it with the Timer's Task", async () => {
    let timer = makeTimer("PomodoroRunning", taskA);
    mockApi(() => timer);
    render(<TasksPanel />);
    await waitFor(() => expect(rowOf("Task A")).toHaveAttribute("aria-current", "true"));

    timer = makeTimer("PomodoroRunning", taskB);
    act(() => broadcastTimerChanged());
    await waitFor(() => expect(rowOf("Task B")).toHaveAttribute("aria-current", "true"));
    expect(rowOf("Task A")).not.toHaveAttribute("aria-current");

    timer = makeTimer("Idle", null);
    act(() => broadcastTimerChanged());
    await waitFor(() => expect(rowOf("Task B")).not.toHaveAttribute("aria-current"));
    expect(rowOf("Task A")).not.toHaveAttribute("aria-current");
  });
});
