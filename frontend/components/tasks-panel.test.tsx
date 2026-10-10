import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { TasksPanel } from "./tasks-panel";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TimerResponseBody = components["schemas"]["TimerResponse"];

const getMock = vi.fn();
const postMock = vi.fn();
const putMock = vi.fn();
const deleteMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    POST: (...args: unknown[]) => postMock(...args),
    PUT: (...args: unknown[]) => putMock(...args),
    DELETE: (...args: unknown[]) => deleteMock(...args),
  },
}));

function ok(status = 200): Response {
  return { status } as Response;
}

function makeTask(overrides: Partial<TaskResponseBody> = {}): TaskResponseBody {
  return {
    id: "task-1",
    text: "Write the report",
    position: 0,
    tag_ids: [],
    created_at: "2026-01-01T00:00:00Z",
    archived_at: null,
    deletable: true,
    ...overrides,
  };
}

function makeTimer(phase: TimerResponseBody["phase"]): TimerResponseBody {
  return {
    phase,
    task: null,
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

function taskRowRect(index: number): DOMRect {
  const top = index * 48;
  return {
    x: 0,
    y: top,
    width: 320,
    height: 40,
    top,
    right: 320,
    bottom: top + 40,
    left: 0,
    toJSON: () => ({}),
  } as DOMRect;
}

interface Fixture {
  activeTasks?: TaskResponseBody[];
  archivedTasks?: TaskResponseBody[];
  tags?: components["schemas"]["TagResponse"][];
  timerPhase?: TimerResponseBody["phase"];
}

function setupFixture({
  activeTasks = [],
  archivedTasks = [],
  tags = [],
  timerPhase = "Idle",
}: Fixture = {}) {
  getMock.mockImplementation((path: string) => {
    if (path === "/api/v1/tags") {
      return Promise.resolve({ data: { tags }, error: undefined, response: ok() });
    }
    if (path === "/api/v1/tasks") {
      return Promise.resolve({
        data: {
          tasks: activeTasks,
          active_count: activeTasks.length,
          archived_count: archivedTasks.length,
        },
        error: undefined,
        response: ok(),
      });
    }
    if (path === "/api/v1/tasks/archived") {
      return Promise.resolve({
        data: {
          tasks: archivedTasks,
          active_count: activeTasks.length,
          archived_count: archivedTasks.length,
        },
        error: undefined,
        response: ok(),
      });
    }
    if (path === "/api/v1/timer") {
      return Promise.resolve({ data: makeTimer(timerPhase), error: undefined, response: ok() });
    }
    throw new Error(`Unexpected GET ${path}`);
  });
}

beforeEach(() => {
  getMock.mockReset();
  postMock.mockReset();
  putMock.mockReset();
  deleteMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TasksPanel — create on Enter", () => {
  it("creates a Task and clears the input on success", async () => {
    setupFixture();
    postMock.mockResolvedValue({
      data: makeTask({ text: "Ship the release" }),
      error: undefined,
      response: ok(201),
    });
    const user = userEvent.setup();

    render(<TasksPanel />);
    const input = await screen.findByLabelText("Nueva tarea");
    await user.type(input, "Ship the release{Enter}");

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith("/api/v1/tasks", {
        body: { text: "Ship the release" },
      });
    });
    expect(input).toHaveValue("");
  });

  it("surfaces a duplicate-text validation error returned by the HTTP interface", async () => {
    setupFixture();
    postMock.mockResolvedValue({
      data: undefined,
      error: {
        detail: "A Task with this text already exists: 'Ship it'.",
        code: "duplicate_task_text",
      },
      response: ok(422),
    });
    const user = userEvent.setup();

    render(<TasksPanel />);
    const input = await screen.findByLabelText("Nueva tarea");
    await user.type(input, "Ship it{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "A Task with this text already exists: 'Ship it'.",
    );
    expect(input).toHaveValue("Ship it");
  });

  it("surfaces an empty-text validation error returned by the HTTP interface", async () => {
    setupFixture();
    postMock.mockResolvedValue({
      data: undefined,
      error: { detail: "Task text cannot be empty.", code: "empty_task_text" },
      response: ok(422),
    });
    const user = userEvent.setup();

    render(<TasksPanel />);
    const input = await screen.findByLabelText("Nueva tarea");
    await user.click(input);
    await user.keyboard("{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("Task text cannot be empty.");
  });
});

describe("TasksPanel — filtering", () => {
  it("requests the Active list with the text query combined with selected Tags", async () => {
    setupFixture({ tags: [{ id: "tag-a", name: "Work" }] });
    const user = userEvent.setup();

    render(<TasksPanel />);
    await screen.findByLabelText("Nueva tarea");
    getMock.mockClear();

    await user.type(screen.getByLabelText("Filtrar Activas"), "repo");
    await user.click(screen.getByRole("button", { name: "Work" }));

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/api/v1/tasks", {
        params: { query: { q: "repo", tags: ["tag-a"] } },
      });
    });
  });
});

describe("TasksPanel — Archived tab", () => {
  it("hides Borrar for a Task with recorded Pomodoros and shows it otherwise", async () => {
    setupFixture({
      archivedTasks: [
        makeTask({ id: "task-undeletable", text: "Has Pomodoros", deletable: false }),
        makeTask({ id: "task-deletable", text: "Never started", deletable: true }),
      ],
    });
    const user = userEvent.setup();

    render(<TasksPanel />);
    await user.click(await screen.findByRole("tab", { name: /Archivadas/ }));

    await screen.findByText("Has Pomodoros");
    expect(screen.getAllByRole("button", { name: "Borrar" })).toHaveLength(1);
  });

  it("surfaces an unarchive collision returned by the HTTP interface", async () => {
    setupFixture({ archivedTasks: [makeTask({ text: "Ship the release" })] });
    postMock.mockResolvedValue({
      data: undefined,
      error: {
        detail: "An Active Task with this text already exists: 'Ship the release'.",
        code: "duplicate_task_text",
      },
      response: ok(422),
    });
    const user = userEvent.setup();

    render(<TasksPanel />);
    await user.click(await screen.findByRole("tab", { name: /Archivadas/ }));
    await user.click(await screen.findByRole("button", { name: "Desarchivar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An Active Task with this text already exists: 'Ship the release'.",
    );
  });
});

describe("TasksPanel — drag-reorder wiring", () => {
  it("renders a drag handle for every Active Task", async () => {
    setupFixture({
      activeTasks: [
        makeTask({ id: "task-1", text: "First" }),
        makeTask({ id: "task-2", text: "Second" }),
      ],
    });

    render(<TasksPanel />);

    expect(await screen.findByRole("button", { name: "Reordenar First" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reordenar Second" })).toBeInTheDocument();
  });

  it("invokes the reorder endpoint with the recomputed order on a drag end", async () => {
    setupFixture({
      activeTasks: [
        makeTask({ id: "task-1", text: "First" }),
        makeTask({ id: "task-2", text: "Second" }),
        makeTask({ id: "task-3", text: "Third" }),
      ],
    });
    putMock.mockResolvedValue({ data: [], error: undefined, response: ok() });
    const user = userEvent.setup();
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
      this: HTMLElement,
    ) {
      const row = this.closest("li");
      const index = row ? Array.from(row.parentElement?.children ?? []).indexOf(row) : 0;
      return taskRowRect(index);
    });

    render(<TasksPanel />);
    const firstHandle = await screen.findByRole("button", { name: "Reordenar First" });
    firstHandle.focus();
    await user.keyboard(" {ArrowDown}{ArrowDown} ");

    await waitFor(() => {
      expect(putMock).toHaveBeenCalledWith("/api/v1/tasks/reorder", {
        body: { task_ids: ["task-2", "task-3", "task-1"] },
      });
    });
  });
});
