import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "@/lib/api/schema";
import { IDLE_TIMER, makeTask } from "./task-fixtures";
import { TasksPanel } from "./tasks-panel";

type TaskResponseBody = components["schemas"]["TaskResponse"];
type TagResponseBody = components["schemas"]["TagResponse"];

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

/** In-memory server: PATCH tags creates missing Tags by normalized name and rewrites the Task. */
function setupServer(tasks: TaskResponseBody[], tags: TagResponseBody[]) {
  getMock.mockImplementation((path: string) => {
    const counts = { active_count: tasks.length, archived_count: 0 };
    const data =
      path === "/api/v1/tags"
        ? { tags: [...tags] }
        : path === "/api/v1/timer"
          ? { ...IDLE_TIMER }
          : { tasks: tasks.map((task) => ({ ...task })), ...counts };
    return Promise.resolve({ data, error: undefined, response: ok() });
  });
  patchMock.mockImplementation(
    (
      _path: string,
      options: { params: { path: { task_id: string } }; body: { names: string[] } },
    ) => {
      const task = tasks.find((candidate) => candidate.id === options.params.path.task_id);
      if (task) {
        task.tag_ids = options.body.names.map((name) => {
          const key = name.trim().toLowerCase();
          let tag = tags.find((candidate) => candidate.name.toLowerCase() === key);
          if (!tag) {
            tag = { id: `tag-${key}`, name: name.trim() } as TagResponseBody;
            tags.push(tag);
          }
          return tag.id;
        });
      }
      return Promise.resolve({ data: task, error: undefined, response: ok() });
    },
  );
}

beforeEach(() => {
  getMock.mockReset();
  patchMock.mockReset();
});

describe("TasksPanel — Task Tag editor", () => {
  it("adds a typed new Tag, shows the chip and the filter chip without reload", async () => {
    setupServer([makeTask("a", "Write report")], []);
    const user = userEvent.setup();
    render(<TasksPanel />);

    const input = await screen.findByRole("combobox", { name: "Agregar etiqueta a Write report" });
    await user.type(input, "  Deep Work {Enter}");

    expect(await screen.findByRole("button", { name: "Quitar etiqueta Deep Work" })).toBeVisible();
    expect(patchMock).toHaveBeenCalledWith("/api/v1/tasks/{task_id}/tags", {
      params: { path: { task_id: "a" } },
      body: { names: ["Deep Work"] },
    });
    const filter = screen.getByRole("group", { name: /Filtrar Activas - Tags/ });
    expect(await within(filter).findByRole("button", { name: "Deep Work" })).toBeVisible();
    expect(input).toHaveValue("");
  });

  it("suggests catalog Tags not already on the Task", async () => {
    setupServer(
      [makeTask("a", "Write report", ["t1"])],
      [
        { id: "t1", name: "Work", color: "rose" as const },
        { id: "t2", name: "Home", color: "rose" as const },
      ],
    );
    render(<TasksPanel />);

    const input = await screen.findByRole("combobox", { name: "Agregar etiqueta a Write report" });
    const list = document.getElementById(input.getAttribute("list") ?? "");
    expect([...(list?.querySelectorAll("option") ?? [])].map((option) => option.value)).toEqual([
      "Home",
    ]);
  });

  it("removes a chip and sends the remaining names", async () => {
    setupServer(
      [makeTask("a", "Write report", ["t1", "t2"])],
      [
        { id: "t1", name: "Work", color: "rose" as const },
        { id: "t2", name: "Home", color: "rose" as const },
      ],
    );
    const user = userEvent.setup();
    render(<TasksPanel />);

    await user.click(await screen.findByRole("button", { name: "Quitar etiqueta Work" }));

    await vi.waitFor(() =>
      expect(screen.queryByRole("button", { name: "Quitar etiqueta Work" })).toBeNull(),
    );
    expect(screen.getByRole("button", { name: "Quitar etiqueta Home" })).toBeVisible();
    expect(patchMock).toHaveBeenCalledWith("/api/v1/tasks/{task_id}/tags", {
      params: { path: { task_id: "a" } },
      body: { names: ["Home"] },
    });
  });

  it("shows a Spanish error, keeps the draft and refocuses the re-enabled input", async () => {
    setupServer([makeTask("a", "Write report")], []);
    let resolvePatch: (value: unknown) => void = () => {};
    patchMock.mockReturnValue(new Promise((resolve) => (resolvePatch = resolve)));
    const user = userEvent.setup();
    render(<TasksPanel />);

    const input = await screen.findByRole("combobox", { name: "Agregar etiqueta a Write report" });
    await user.type(input, "x{Enter}");
    // A real browser drops focus from an input that becomes disabled; jsdom does not.
    await vi.waitFor(() => expect(input).toBeDisabled());
    const elsewhere = document.createElement("button");
    document.body.append(elsewhere);
    elsewhere.focus();
    expect(input).not.toHaveFocus();

    resolvePatch({
      data: undefined,
      error: { detail: "English detail", code: "empty_tag_name" },
      response: ok(422),
    });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("El nombre de la etiqueta no puede estar vacío.");
    expect(alert).toHaveClass("dark:text-red-400");
    expect(input).toHaveValue("x");
    await vi.waitFor(() => expect(input).toHaveFocus());
    elsewhere.remove();
  });

  it.each([
    ["duplicate_tag_name", /ya existe/i],
    ["tag_not_found", /no existe|no se encontr/i],
  ])("renders the Spanish message for %s", async (code, expected) => {
    setupServer([makeTask("a", "Write report")], []);
    patchMock.mockResolvedValue({
      data: undefined,
      error: { detail: "English detail", code },
      response: ok(409),
    });
    const user = userEvent.setup();
    render(<TasksPanel />);

    const input = await screen.findByRole("combobox", { name: "Agregar etiqueta a Write report" });
    await user.type(input, "x{Enter}");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(expected);
    expect(alert).not.toHaveTextContent("English detail");
  });

  it("moves focus to the add input after removing a chip", async () => {
    setupServer(
      [makeTask("a", "Write report", ["t1"])],
      [{ id: "t1", name: "Work", color: "rose" as const }],
    );
    const user = userEvent.setup();
    render(<TasksPanel />);

    const remove = await screen.findByRole("button", { name: "Quitar etiqueta Work" });
    await vi.waitFor(() => expect(remove).toBeEnabled());
    await user.click(remove);

    const input = screen.getByRole("combobox", { name: "Agregar etiqueta a Write report" });
    await vi.waitFor(() => expect(input).toHaveFocus());
  });

  it("disables add and remove until the catalog resolves the Task's Tag names", async () => {
    setupServer(
      [makeTask("a", "Write report", ["t1"])],
      [{ id: "t1", name: "Work", color: "rose" as const }],
    );
    let releaseCatalog: () => void = () => {};
    const catalogGate = new Promise<void>((resolve) => (releaseCatalog = resolve));
    const serve = getMock.getMockImplementation();
    getMock.mockImplementation(async (path: string, ...rest: unknown[]) => {
      if (path === "/api/v1/tags") {
        await catalogGate;
      }
      return serve?.(path, ...rest);
    });
    render(<TasksPanel />);

    const input = await screen.findByRole("combobox", { name: "Agregar etiqueta a Write report" });
    expect(input).toBeDisabled();
    expect(screen.getByRole("button", { name: /Quitar etiqueta/ })).toBeDisabled();

    releaseCatalog();
    expect(await screen.findByRole("button", { name: "Quitar etiqueta Work" })).toBeEnabled();
    expect(input).toBeEnabled();
  });
});
