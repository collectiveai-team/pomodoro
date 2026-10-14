import { act, render, screen, waitFor, within } from "@testing-library/react";
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
const failed = { status: 422 } as Response;

/** In-memory server for Tags and Tasks: rename rejects duplicates, delete strips the Tag from Tasks. */
function setupServer(tasks: TaskResponseBody[], tags: TagResponseBody[]) {
  getMock.mockImplementation((path: string) => {
    const data =
      path === "/api/v1/tags"
        ? { tags: tags.map((tag) => ({ ...tag })) }
        : path === "/api/v1/timer"
          ? { ...IDLE_TIMER }
          : {
              tasks: tasks.map((task) => ({ ...task })),
              active_count: tasks.length,
              archived_count: 0,
            };
    return Promise.resolve({ data, error: undefined, response: ok });
  });
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
      return Promise.resolve({ data: undefined, error: undefined, response: ok });
    },
  );
}

function setupRename(tags: TagResponseBody[]) {
  patchMock.mockImplementation(
    (_path: string, options: { params: { path: { tag_id: string } }; body: { name: string } }) => {
      const name = options.body.name.trim();
      if (tags.some((tag) => tag.name.toLowerCase() === name.toLowerCase())) {
        return Promise.resolve({
          data: undefined,
          error: { detail: "Tag name already exists", code: "duplicate_tag_name" },
          response: failed,
        });
      }
      const tag = tags.find((candidate) => candidate.id === options.params.path.tag_id);
      if (tag) {
        tag.name = name;
      }
      return Promise.resolve({ data: tag, error: undefined, response: ok });
    },
  );
}

const WORK = { id: "t1", name: "Work", color: "rose" as const };
const HOME = { id: "t2", name: "Home", color: "rose" as const };

async function openManager(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: "Etiquetas" }));
  return screen.getByRole("region", { name: "Gestionar etiquetas" });
}

/** Opens the manager, waits for the Tag to list, and starts renaming it. */
async function startRename(user: ReturnType<typeof userEvent.setup>, name: string) {
  const manager = await openManager(user);
  await within(manager).findByText(name);
  await user.click(within(manager).getByRole("button", { name: `Renombrar etiqueta ${name}` }));
  return {
    manager,
    input: screen.getByRole("textbox", { name: `Nuevo nombre de la etiqueta ${name}` }),
  };
}

beforeEach(() => {
  getMock.mockReset();
  patchMock.mockReset();
  deleteMock.mockReset();
});

async function rowOf(): Promise<HTMLElement> {
  const row = (await screen.findByText("Write report")).closest("li");
  if (!row) throw new Error("no row");
  return row;
}

describe("TasksPanel — Tag manager", () => {
  it("renames a Tag on Task chips and filter chips without reload", async () => {
    const tags = [{ ...WORK }, { ...HOME }];
    setupServer([makeTask("a", "Write report", ["t1"])], tags);
    setupRename(tags);
    const user = userEvent.setup();
    render(<TasksPanel />);

    const { input } = await startRename(user, "Work");
    await user.clear(input);
    await user.type(input, "Deep Work{Enter}");

    expect(patchMock).toHaveBeenCalledWith("/api/v1/tags/{tag_id}", {
      params: { path: { tag_id: "t1" } },
      body: { name: "Deep Work" },
    });
    const filter = screen.getByRole("group", { name: /Filtrar Activas - Tags/ });
    expect(await within(filter).findByRole("button", { name: "Deep Work" })).toBeVisible();
    expect(await within(await rowOf()).findByText("Deep Work")).toBeVisible();
    expect(within(filter).queryByRole("button", { name: "Work" })).toBeNull();
  });

  it("shows the Spanish duplicate message, keeps the old name and keeps focus", async () => {
    const tags = [{ ...WORK }, { ...HOME }];
    setupServer([], tags);
    setupRename(tags);
    const user = userEvent.setup();
    render(<TasksPanel />);

    const { manager, input } = await startRename(user, "Work");
    await user.clear(input);
    await user.type(input, "home{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya existe una etiqueta con ese nombre.",
    );
    expect(tags[0]?.name).toBe("Work");
    await waitFor(() => expect(input).toHaveFocus());

    await user.keyboard("{Escape}");
    expect(await within(manager).findByText("Work")).toBeVisible();
    expect(screen.queryByRole("textbox", { name: /Nuevo nombre/ })).toBeNull();
  });

  it("restores focus after a save that blurred the pending input", async () => {
    const tags = [{ ...WORK }];
    setupServer([], tags);
    let release: (value: unknown) => void = () => {};
    patchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<TasksPanel />);

    const { input } = await startRename(user, "Work");
    await user.type(input, "x{Enter}");
    await waitFor(() => expect(input).toBeDisabled());

    // Real browsers drop focus from an input that becomes disabled; jsdom does not.
    act(() => screen.getByRole("searchbox", { name: "Filtrar Activas" }).focus());
    expect(input).not.toHaveFocus();
    expect(screen.getByRole("textbox", { name: /Nuevo nombre/ })).toBe(input);

    await act(async () => {
      release({
        data: undefined,
        error: { detail: "Tag name already exists", code: "duplicate_tag_name" },
        response: failed,
      });
    });
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("cancels rename on blur outside the form and when Cancelar is clicked", async () => {
    setupServer([], [{ ...WORK }]);
    const user = userEvent.setup();
    render(<TasksPanel />);

    const { manager } = await startRename(user, "Work");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("textbox", { name: /Nuevo nombre/ })).toBeNull();

    await user.click(within(manager).getByRole("button", { name: "Renombrar etiqueta Work" }));
    await user.click(screen.getByRole("searchbox", { name: "Filtrar Activas" }));
    expect(screen.queryByRole("textbox", { name: /Nuevo nombre/ })).toBeNull();
    expect(patchMock).not.toHaveBeenCalled();
  });

  it("deletes without confirmation and drops the Tag from rows, chips and the active filter", async () => {
    const tags = [{ ...WORK }, { ...HOME }];
    setupServer([makeTask("a", "Write report", ["t1", "t2"])], tags);
    const user = userEvent.setup();
    render(<TasksPanel />);

    const filter = await screen.findByRole("group", { name: /Filtrar Activas - Tags/ });
    await user.click(await within(filter).findByRole("button", { name: "Work" }));
    expect(within(filter).getByRole("button", { name: "Work" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const manager = await openManager(user);
    await user.click(within(manager).getByRole("button", { name: "Eliminar etiqueta Work" }));

    const row = await rowOf();
    await waitFor(() => expect(within(row).queryByText("Work")).toBeNull());
    expect(deleteMock).toHaveBeenCalledWith("/api/v1/tags/{tag_id}", {
      params: { path: { tag_id: "t1" } },
    });
    expect(within(filter).queryByRole("button", { name: "Work" })).toBeNull();
    expect(within(row).getByText("Home")).toBeVisible();
    expect(within(filter).getByRole("button", { name: "Sin etiqueta" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await waitFor(() => {
      const lastTaskList = getMock.mock.calls.filter(([path]) => path === "/api/v1/tasks").at(-1);
      expect(lastTaskList?.[1]).toEqual({ params: { query: {} } });
    });
  });

  it("shows the Spanish message when the Tag no longer exists", async () => {
    setupServer([], [{ ...WORK }]);
    deleteMock.mockResolvedValue({
      data: undefined,
      error: { detail: "Tag not found", code: "tag_not_found" },
      response: { status: 404 } as Response,
    });
    const user = userEvent.setup();
    render(<TasksPanel />);

    const manager = await openManager(user);
    await user.click(
      await within(manager).findByRole("button", { name: "Eliminar etiqueta Work" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("No se encontró la etiqueta.");
  });
});
