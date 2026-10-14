import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { snapshotFromEvent, TIMER_CHANGED_EVENT } from "@/lib/timer-sync";
import { TasksPanel } from "./tasks-panel";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TimerResponseBody = components["schemas"]["TimerResponse"];

const getMock = vi.fn();
const patchMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    PATCH: (...args: unknown[]) => patchMock(...args),
  },
}));

function ok(status = 200): Response {
  return { status } as Response;
}

function makeTask(id: string, text: string, archived = false): TaskResponseBody {
  return {
    id,
    text,
    position: 0,
    tag_ids: [],
    created_at: "2026-01-01T00:00:00Z",
    archived_at: archived ? "2026-01-02T00:00:00Z" : null,
    deletable: true,
  };
}

function makeTimer(phase: TimerResponseBody["phase"], task: TaskResponseBody | null) {
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
  } satisfies TimerResponseBody;
}

/** A tiny in-memory server: PATCH rewrites the stored Task text, GETs read it back. */
function setupServer(tasks: TaskResponseBody[], timerTaskId: string | null = null) {
  getMock.mockImplementation((path: string) => {
    const active = tasks.filter((task) => task.archived_at === null);
    const archived = tasks.filter((task) => task.archived_at !== null);
    const counts = { active_count: active.length, archived_count: archived.length };
    const timerTask = tasks.find((task) => task.id === timerTaskId) ?? null;
    const data =
      path === "/api/v1/tags"
        ? { tags: [] }
        : path === "/api/v1/timer"
          ? makeTimer(timerTask ? "PomodoroRunning" : "Idle", timerTask)
          : path === "/api/v1/tasks"
            ? { tasks: active, ...counts }
            : { tasks: archived, ...counts };
    return Promise.resolve({ data, error: undefined, response: ok() });
  });
  patchMock.mockImplementation(
    (_path: string, options: { params: { path: { task_id: string } }; body: { text: string } }) => {
      const task = tasks.find((candidate) => candidate.id === options.params.path.task_id);
      if (task) {
        task.text = options.body.text;
      }
      return Promise.resolve({ data: task, error: undefined, response: ok() });
    },
  );
}

function failPatchWith(code: string) {
  patchMock.mockResolvedValue({
    data: undefined,
    error: { detail: "English detail", code },
    response: ok(422),
  });
}

beforeEach(() => {
  getMock.mockReset();
  patchMock.mockReset();
});
afterEach(() => vi.restoreAllMocks());

describe("TasksPanel — inline edit of Task text", () => {
  it("saves an Active Task's new text on Enter and shows it in the row", async () => {
    setupServer([makeTask("a", "Old text")]);
    const user = userEvent.setup();
    render(<TasksPanel />);

    await user.click(await screen.findByRole("button", { name: "Acciones de Old text" }));
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    const input = screen.getByRole("textbox", { name: "Editar texto de la tarea" });
    await user.clear(input);
    await user.type(input, "New text{Enter}");

    expect(await screen.findByText("New text")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Editar texto de la tarea" })).toBeNull();
    expect(patchMock).toHaveBeenCalledWith("/api/v1/tasks/{task_id}", {
      params: { path: { task_id: "a" } },
      body: { text: "New text" },
    });
  });

  it("saves an Archived Task's new text through the Guardar button", async () => {
    setupServer([makeTask("z", "Archived old", true)]);
    const user = userEvent.setup();
    render(<TasksPanel />);

    await user.click(await screen.findByRole("tab", { name: /Archivadas/ }));
    await user.click(await screen.findByRole("button", { name: "Acciones de Archived old" }));
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    const input = screen.getByRole("textbox", { name: "Editar texto de la tarea" });
    await user.clear(input);
    await user.type(input, "Archived new");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Archived new")).toBeInTheDocument();
  });

  it.each([
    ["empty_task_text", "El texto de la tarea no puede estar vacío."],
    ["task_text_too_long", "El texto de la tarea es demasiado largo."],
    ["duplicate_task_text", "Ya existe una tarea activa con ese texto."],
  ])("shows the Spanish message for %s and keeps the previous text", async (code, message) => {
    setupServer([makeTask("a", "Keep me")]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    await user.click(await screen.findByRole("button", { name: "Acciones de Keep me" }));
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    failPatchWith(code);
    await user.type(screen.getByRole("textbox", { name: "Editar texto de la tarea" }), "x{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("textbox", { name: "Editar texto de la tarea" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(await screen.findByText("Keep me")).toBeInTheDocument();
  });

  it("cancels on Escape without sending a request", async () => {
    setupServer([makeTask("a", "Untouched")]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    await user.click(await screen.findByRole("button", { name: "Acciones de Untouched" }));
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    await user.type(screen.getByRole("textbox", { name: "Editar texto de la tarea" }), "zzz");
    await user.keyboard("{Escape}");

    expect(await screen.findByText("Untouched")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Editar texto de la tarea" })).toBeNull();
    expect(patchMock).not.toHaveBeenCalled();
  });

  it("cancels without a request when focus leaves the editor", async () => {
    setupServer([makeTask("a", "Blurred")]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    await user.click(await screen.findByRole("button", { name: "Acciones de Blurred" }));
    await user.click(screen.getByRole("menuitem", { name: "Editar" }));
    await user.click(screen.getByRole("tab", { name: /Activas/ }));

    expect(await screen.findByText("Blurred")).toBeInTheDocument();
    expect(patchMock).not.toHaveBeenCalled();
  });

  it("broadcasts a bare Timer change when editing the Timer's Task, and not for another Task", async () => {
    setupServer([makeTask("a", "Timer task"), makeTask("b", "Other task")], "a");
    const events: Event[] = [];
    const listener = (event: Event) => events.push(event);
    window.addEventListener(TIMER_CHANGED_EVENT, listener);
    try {
      const user = userEvent.setup();
      render(<TasksPanel />);
      await waitFor(() =>
        expect(screen.getByText("Timer task").closest("li")).toHaveAttribute("aria-current"),
      );

      await user.click(screen.getByRole("button", { name: "Acciones de Other task" }));
      await user.click(screen.getByRole("menuitem", { name: "Editar" }));
      await user.type(
        screen.getByRole("textbox", { name: "Editar texto de la tarea" }),
        "!{Enter}",
      );
      expect(await screen.findByText("Other task!")).toBeInTheDocument();
      expect(events).toHaveLength(0);

      await user.click(screen.getByRole("button", { name: "Acciones de Timer task" }));
      await user.click(screen.getByRole("menuitem", { name: "Editar" }));
      await user.type(
        screen.getByRole("textbox", { name: "Editar texto de la tarea" }),
        "!{Enter}",
      );
      expect(await screen.findByText("Timer task!")).toBeInTheDocument();
      expect(events).toHaveLength(1);
      expect(snapshotFromEvent(events[0] as Event)).toBeNull();
    } finally {
      window.removeEventListener(TIMER_CHANGED_EVENT, listener);
    }
  });
});
