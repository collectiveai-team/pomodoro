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
const deleteMock = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    GET: (...args: unknown[]) => getMock(...args),
    PATCH: (...args: unknown[]) => patchMock(...args),
    DELETE: (...args: unknown[]) => deleteMock(...args),
  },
}));

const ok = { status: 200 } as Response;

function result(data: unknown) {
  return Promise.resolve({ data, error: undefined, response: ok });
}

/** In-memory server: Tasks carry Tag ids; PATCH task tags creates missing Tags by name. */
function setupServer(tasks: TaskResponseBody[], tags: TagResponseBody[]) {
  getMock.mockImplementation((path: string) =>
    result(
      path === "/api/v1/tags"
        ? { tags: tags.map((tag) => ({ ...tag })) }
        : path === "/api/v1/timer"
          ? { ...IDLE_TIMER }
          : {
              tasks: tasks.map((task) => ({ ...task })),
              active_count: tasks.length,
              archived_count: 0,
            },
    ),
  );
  patchMock.mockImplementation(
    (
      path: string,
      options: { params: { path: Record<string, string> }; body: Record<string, unknown> },
    ) => {
      if (path === "/api/v1/tasks/{task_id}/tags") {
        const task = tasks.find((candidate) => candidate.id === options.params.path.task_id);
        const names = options.body.names as string[];
        if (task) {
          task.tag_ids = names.map((name) => {
            let tag = tags.find((c) => c.name.toLowerCase() === name.toLowerCase());
            if (!tag) {
              tag = { id: `tag-${name.toLowerCase()}`, name, color: "sky" };
              tags.push(tag);
            }
            return tag.id;
          });
        }
        return result(task);
      }
      const tag = tags.find((candidate) => candidate.id === options.params.path.tag_id);
      Object.assign(tag ?? {}, options.body);
      return result(tag);
    },
  );
  deleteMock.mockImplementation(
    (_path: string, options: { params: { path: { tag_id: string } } }) => {
      const id = options.params.path.tag_id;
      tags.splice(
        tags.findIndex((tag) => tag.id === id),
        1,
      );
      for (const task of tasks) {
        task.tag_ids = task.tag_ids.filter((tagId) => tagId !== id);
      }
      return result(undefined);
    },
  );
}

const WORK: TagResponseBody = { id: "t1", name: "Work", color: "rose" };
/** Row Tag pills named `name`; the popover now lives inside the row, so skip its entries. */
function rowPills(row: HTMLElement, name: string): HTMLElement[] {
  return within(row)
    .queryAllByText(name)
    .filter((element) => element.closest('[role="dialog"]') === null);
}

const HOME: TagResponseBody = { id: "t2", name: "Home", color: "green" };

async function openPopover(user: ReturnType<typeof userEvent.setup>, taskText: string) {
  await user.click(await screen.findByRole("button", { name: `Etiquetas de ${taskText}` }));
  return screen.findByRole("dialog", { name: `Etiquetas de ${taskText}` });
}

/** Serves one Task, renders the panel and opens that Task's Tag popover. */
async function setupPopover(tags: TagResponseBody[], tagIds: string[] = []) {
  setupServer([makeTask("a", "Write report", tagIds)], tags);
  const user = userEvent.setup();
  render(<TasksPanel />);
  const dialog = await openPopover(user, "Write report");
  return { user, dialog };
}

async function typeInFilter(
  user: ReturnType<typeof userEvent.setup>,
  dialog: HTMLElement,
  text: string,
) {
  const input = within(dialog).getByRole("textbox", { name: "Filtrar o crear etiqueta" });
  await user.type(input, text);
  return input;
}

beforeEach(() => {
  getMock.mockReset();
  patchMock.mockReset();
  deleteMock.mockReset();
});

describe("Tag popover", () => {
  it("opens for the Task whose 🏷 was clicked and no other", async () => {
    setupServer([makeTask("a", "Write report"), makeTask("b", "Water plants")], [WORK]);
    const user = userEvent.setup();
    render(<TasksPanel />);

    const dialog = await openPopover(user, "Water plants");

    expect(dialog).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "Etiquetas de Write report" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Etiquetas$/ })).toBeNull();
  });

  it("anchors the popover inside the row of the Task whose 🏷 opened it", async () => {
    setupServer([makeTask("a", "Write report", []), makeTask("b", "Water plants", [])], [WORK]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    const row = (await screen.findByText("Water plants")).closest("li") as HTMLElement;

    const dialog = await openPopover(user, "Water plants");

    expect(row).toContainElement(dialog);
  });

  it("closes the popover when its own 🏷 is clicked again", async () => {
    setupServer([makeTask("a", "Write report", [])], [WORK]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    await openPopover(user, "Write report");

    await user.click(screen.getByRole("button", { name: "Etiquetas de Write report" }));

    expect(screen.queryByRole("dialog", { name: "Etiquetas de Write report" })).toBeNull();
  });

  it("marks assigned Tags and toggles assignment on click, updating the row pills", async () => {
    setupServer([makeTask("a", "Write report", ["t1"])], [WORK, HOME]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    const row = (await screen.findByText("Write report")).closest("li") as HTMLElement;
    expect(within(row).getByText("Work")).toBeVisible();

    const dialog = await openPopover(user, "Write report");
    expect(within(dialog).getByRole("button", { name: "Etiqueta Work" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(within(dialog).getByRole("button", { name: "Etiqueta Home" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    await user.click(within(dialog).getByRole("button", { name: "Etiqueta Home" }));
    expect(patchMock).toHaveBeenCalledWith("/api/v1/tasks/{task_id}/tags", {
      params: { path: { task_id: "a" } },
      body: { names: ["Work", "Home"] },
    });
    await vi.waitFor(() => expect(rowPills(row, "Home")).toHaveLength(1));

    await user.click(within(dialog).getByRole("button", { name: "Etiqueta Work" }));
    await vi.waitFor(() => expect(rowPills(row, "Work")).toHaveLength(0));
    expect(rowPills(row, "Home")).toHaveLength(1);
  });

  it("filters the list while typing", async () => {
    const { user, dialog } = await setupPopover([WORK, HOME]);

    await typeInFilter(user, dialog, "ho");

    expect(within(dialog).getByRole("button", { name: "Etiqueta Home" })).toBeVisible();
    expect(within(dialog).queryByRole("button", { name: "Etiqueta Work" })).toBeNull();
  });

  it("creates and assigns a new Tag with Enter", async () => {
    const { user, dialog } = await setupPopover([WORK]);

    const input = await typeInFilter(user, dialog, "Deep Work{Enter}");

    expect(patchMock).toHaveBeenCalledWith("/api/v1/tasks/{task_id}/tags", {
      params: { path: { task_id: "a" } },
      body: { names: ["Deep Work"] },
    });
    const pressed = await within(dialog).findByRole("button", { name: "Etiqueta Deep Work" });
    expect(pressed).toHaveAttribute("aria-pressed", "true");
    expect(input).toHaveValue("");
  });

  it("Enter on an existing name only assigns it, without creating a duplicate", async () => {
    const tags = [WORK, HOME];
    setupServer([makeTask("a", "Write report")], tags);
    const user = userEvent.setup();
    render(<TasksPanel />);
    const dialog = await openPopover(user, "Write report");

    await typeInFilter(user, dialog, "home{Enter}");

    expect(patchMock).toHaveBeenCalledWith("/api/v1/tasks/{task_id}/tags", {
      params: { path: { task_id: "a" } },
      body: { names: ["Home"] },
    });
    expect(tags).toHaveLength(2);
  });

  it("renames a Tag keeping its color", async () => {
    const { user, dialog } = await setupPopover([{ ...WORK }], ["t1"]);

    await user.click(within(dialog).getByRole("button", { name: "Editar etiqueta Work" }));
    const input = within(dialog).getByRole("textbox", { name: "Nuevo nombre de la etiqueta Work" });
    await user.clear(input);
    await user.type(input, "Job{Enter}");

    expect(patchMock).toHaveBeenCalledWith("/api/v1/tags/{tag_id}", {
      params: { path: { tag_id: "t1" } },
      body: { name: "Job" },
    });
    expect(await within(dialog).findByRole("button", { name: "Etiqueta Job" })).toBeVisible();
    expect(patchMock.mock.calls.at(-1)?.[1].body).not.toHaveProperty("color");
  });

  it("offers the 8 palette colors and changes the Tag color", async () => {
    const { user, dialog } = await setupPopover([{ ...WORK }], ["t1"]);

    await user.click(within(dialog).getByRole("button", { name: "Editar etiqueta Work" }));
    const palette = within(dialog).getByRole("group", { name: "Color de la etiqueta Work" });
    expect(within(palette).getAllByRole("button")).toHaveLength(8);
    await user.click(within(palette).getByRole("button", { name: "Color Violeta" }));

    expect(patchMock).toHaveBeenCalledWith("/api/v1/tags/{tag_id}", {
      params: { path: { tag_id: "t1" } },
      body: { color: "violet" },
    });
    expect(
      await within(dialog).findByRole("button", { name: "Color Violeta", pressed: true }),
    ).toBeVisible();
  });

  it("deletes a Tag from the catalog and the rows", async () => {
    setupServer([makeTask("a", "Write report", ["t1"])], [{ ...WORK }]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    const row = (await screen.findByText("Write report")).closest("li") as HTMLElement;
    const dialog = await openPopover(user, "Write report");

    await user.click(within(dialog).getByRole("button", { name: "Editar etiqueta Work" }));
    await user.click(within(dialog).getByRole("button", { name: "Eliminar etiqueta Work" }));

    expect(deleteMock).toHaveBeenCalledWith("/api/v1/tags/{tag_id}", {
      params: { path: { tag_id: "t1" } },
    });
    await vi.waitFor(() => expect(within(row).queryByText("Work")).toBeNull());
    expect(within(dialog).queryByRole("button", { name: "Etiqueta Work" })).toBeNull();
  });

  it("shows the Spanish error when the API rejects a change", async () => {
    setupServer([makeTask("a", "Write report", ["t1"])], [{ ...WORK }]);
    patchMock.mockResolvedValue({
      data: undefined,
      error: { detail: "English detail", code: "duplicate_tag_name" },
      response: { status: 409 } as Response,
    });
    const user = userEvent.setup();
    render(<TasksPanel />);
    const dialog = await openPopover(user, "Write report");

    await typeInFilter(user, dialog, "x{Enter}");

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(/ya existe/i);
  });

  it("closes with Esc and with a click outside", async () => {
    setupServer([makeTask("a", "Write report")], [WORK]);
    const user = userEvent.setup();
    render(<TasksPanel />);
    await openPopover(user, "Write report");

    await user.keyboard("{Escape}");
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await openPopover(user, "Write report");
    await user.click(screen.getByRole("tab", { name: /Archivadas/ }));
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
