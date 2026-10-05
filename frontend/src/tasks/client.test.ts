import { afterEach, describe, expect, it, vi } from "vitest";
import {
  expectRequest,
  jsonResponse,
  stubSameOriginFetch,
} from "@/src/testing/fetch-stub";

async function importTasksClientWithFetch(fetchMock: typeof fetch) {
  stubSameOriginFetch(fetchMock);
  return import("./client");
}

const TASK_BODY = {
  id: 1,
  text: "Write the panel",
  position: 0,
  tags: ["trabajo"],
  created_at: "2026-01-01T00:00:00.000Z",
  archived_at: null,
  deletable: true,
};

describe("tasks client wrappers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("requests the Active list with the text/tags query combined with AND/OR per filter_tasks", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse([TASK_BODY]),
    );
    const { fetchActiveTasks } = await importTasksClientWithFetch(fetchMock);

    const result = await fetchActiveTasks({
      text: "write",
      tags: ["trabajo", "sin etiqueta"],
    });

    const request = expectRequest(fetchMock, "GET", "/api/tasks/active");
    const url = new URL(request.url);
    expect(url.searchParams.get("text")).toBe("write");
    expect(url.searchParams.getAll("tags")).toEqual([
      "trabajo",
      "sin etiqueta",
    ]);
    expect(result).toEqual({ ok: true, tasks: [TASK_BODY] });
  });

  it("creates a Task via a real POST carrying text and tags in the body", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(TASK_BODY, 201),
    );
    const { createTask } = await importTasksClientWithFetch(fetchMock);

    const result = await createTask("Write the panel", ["trabajo"]);

    const request = expectRequest(fetchMock, "POST", "/api/tasks");
    expect(request.headers.get("content-type")).toBe("application/json");
    const body = await request.clone().json();
    expect(body).toEqual({ text: "Write the panel", tags: ["trabajo"] });
    expect(result).toEqual({ ok: true, task: TASK_BODY });
  });

  it("surfaces the server's duplicate-text message on a 409 instead of a generic fallback", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(
        { detail: "Ya existe una tarea activa con ese texto." },
        409,
      ),
    );
    const { createTask } = await importTasksClientWithFetch(fetchMock);

    const result = await createTask("Write the panel");

    expect(result).toEqual({
      ok: false,
      status: 409,
      message: "Ya existe una tarea activa con ese texto.",
    });
  });

  it("archives a Task via a body-less POST that still carries Content-Type for csrf_guard", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(TASK_BODY));
    const { archiveTask } = await importTasksClientWithFetch(fetchMock);

    const result = await archiveTask(1);

    const request = expectRequest(fetchMock, "POST", "/api/tasks/1/archive");
    expect(request.headers.get("content-type")).toBe("application/json");
    expect(result).toEqual({ ok: true, task: TASK_BODY });
  });

  it("surfaces the in-progress rejection clearly when archiving the Task the Timer is running on", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(
        { detail: "No se puede archivar ni borrar la tarea en curso." },
        409,
      ),
    );
    const { archiveTask } = await importTasksClientWithFetch(fetchMock);

    const result = await archiveTask(1);

    expect(result).toEqual({
      ok: false,
      status: 409,
      message: "No se puede archivar ni borrar la tarea en curso.",
    });
  });

  it("reorders Tasks via a real POST carrying the full ordered id list", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse([TASK_BODY]),
    );
    const { reorderTasks } = await importTasksClientWithFetch(fetchMock);

    const result = await reorderTasks([3, 1, 2]);

    const request = expectRequest(fetchMock, "POST", "/api/tasks/reorder");
    const body = await request.clone().json();
    expect(body).toEqual({ task_ids: [3, 1, 2] });
    expect(result).toEqual({ ok: true, tasks: [TASK_BODY] });
  });

  it("edits a Task's Tags via a real PATCH to the per-task endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(TASK_BODY));
    const { editTaskTags } = await importTasksClientWithFetch(fetchMock);

    const result = await editTaskTags(1, ["trabajo", "urgente"]);

    const request = expectRequest(fetchMock, "PATCH", "/api/tasks/1/tags");
    const body = await request.clone().json();
    expect(body).toEqual({ tags: ["trabajo", "urgente"] });
    expect(result).toEqual({ ok: true, task: TASK_BODY });
  });

  it("fetches the Tag catalog via a real GET request", async () => {
    const catalog = [{ id: 1, name: "trabajo" }];
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(catalog));
    const { fetchTagCatalog } = await importTasksClientWithFetch(fetchMock);

    const result = await fetchTagCatalog();

    expectRequest(fetchMock, "GET", "/api/tags");
    expect(result).toEqual(catalog);
  });

  it("requests the Archived list with the same text/tags query as Active", async () => {
    const archivedBody = {
      ...TASK_BODY,
      archived_at: "2026-01-02T00:00:00.000Z",
    };
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse([archivedBody]),
    );
    const { fetchArchivedTasks } = await importTasksClientWithFetch(fetchMock);

    const result = await fetchArchivedTasks({
      text: "write",
      tags: ["trabajo", "sin etiqueta"],
    });

    const request = expectRequest(fetchMock, "GET", "/api/tasks/archived");
    const url = new URL(request.url);
    expect(url.searchParams.get("text")).toBe("write");
    expect(url.searchParams.getAll("tags")).toEqual([
      "trabajo",
      "sin etiqueta",
    ]);
    expect(result).toEqual({ ok: true, tasks: [archivedBody] });
  });

  it("unarchives a Task via a body-less POST that still carries Content-Type for csrf_guard", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(TASK_BODY));
    const { unarchiveTask } = await importTasksClientWithFetch(fetchMock);

    const result = await unarchiveTask(1);

    const request = expectRequest(fetchMock, "POST", "/api/tasks/1/unarchive");
    expect(request.headers.get("content-type")).toBe("application/json");
    expect(result).toEqual({ ok: true, task: TASK_BODY });
  });

  it("surfaces the server's text-collision message when unarchiving conflicts with an Active Task", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(
        { detail: "Ya existe una tarea activa con ese texto." },
        409,
      ),
    );
    const { unarchiveTask } = await importTasksClientWithFetch(fetchMock);

    const result = await unarchiveTask(1);

    expect(result).toEqual({
      ok: false,
      status: 409,
      message: "Ya existe una tarea activa con ese texto.",
    });
  });

  it("deletes a Task via a body-less DELETE that still carries Content-Type for csrf_guard", async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 204 }),
    );
    const { deleteTask } = await importTasksClientWithFetch(fetchMock);

    const result = await deleteTask(1);

    const request = expectRequest(fetchMock, "DELETE", "/api/tasks/1");
    expect(request.headers.get("content-type")).toBe("application/json");
    expect(result).toEqual({ ok: true });
  });

  it("surfaces the server's has-Pomodoros rejection when deleting an undeletable Task", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(
        { detail: "No se puede borrar una tarea con Pomodoros registrados." },
        409,
      ),
    );
    const { deleteTask } = await importTasksClientWithFetch(fetchMock);

    const result = await deleteTask(1);

    expect(result).toEqual({
      ok: false,
      status: 409,
      message: "No se puede borrar una tarea con Pomodoros registrados.",
    });
  });

  it("fetches the tab counts via a real GET request", async () => {
    const counts = { active: 3, archived: 1 };
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(counts));
    const { fetchTaskCounts } = await importTasksClientWithFetch(fetchMock);

    const result = await fetchTaskCounts();

    expectRequest(fetchMock, "GET", "/api/tasks/summary");
    expect(result).toEqual(counts);
  });
});
