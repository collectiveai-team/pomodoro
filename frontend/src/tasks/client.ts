import { apiClient } from "@/src/api/client";
import type { components } from "@/src/api/schema";
import { extractErrorMessage } from "@/src/auth/messages";

/**
 * Generated-client wrappers for the `/api/tasks` and `/api/tags` surface
 * `ActiveTab` (T24) and `ArchivedTab` (T25) depend on: listing (filtered),
 * creating, editing a Task's Tags, reordering, archiving/unarchiving,
 * deleting, the tab counts, and the Tag catalog the filter's chips are built
 * from.
 */

export type TaskPublic = components["schemas"]["TaskPublic"];
export type TagPublic = components["schemas"]["TagPublic"];
export type TaskCounts = components["schemas"]["TaskCountsPublic"];

export type TaskFilterQuery = {
  text: string;
  tags: string[];
};

export type TaskActionResult =
  | { ok: true; task: TaskPublic }
  | { ok: false; status: number; message: string };

export type TaskListResult =
  | { ok: true; tasks: TaskPublic[] }
  | { ok: false; status: number; message: string };

export type ReorderResult =
  | { ok: true; tasks: TaskPublic[] }
  | { ok: false; status: number; message: string };

export type DeleteResult =
  | { ok: true }
  | { ok: false; status: number; message: string };

async function runTaskAction(
  call: () => Promise<{
    data?: TaskPublic;
    error?: unknown;
    response: Response;
  }>,
  fallbackMessage: string,
): Promise<TaskActionResult> {
  const { data, error, response } = await call();
  if (data) {
    return { ok: true, task: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, fallbackMessage),
  };
}

async function fetchTaskList(
  path: "/api/tasks/active" | "/api/tasks/archived",
  filter: TaskFilterQuery,
  fallbackMessage: string,
): Promise<TaskListResult> {
  const { data, error, response } = await apiClient.GET(path, {
    params: { query: { text: filter.text, tags: filter.tags } },
  });
  if (data) {
    return { ok: true, tasks: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, fallbackMessage),
  };
}

export function fetchActiveTasks(
  filter: TaskFilterQuery,
): Promise<TaskListResult> {
  return fetchTaskList(
    "/api/tasks/active",
    filter,
    "No se pudieron cargar las tareas.",
  );
}

export function fetchArchivedTasks(
  filter: TaskFilterQuery,
): Promise<TaskListResult> {
  return fetchTaskList(
    "/api/tasks/archived",
    filter,
    "No se pudieron cargar las tareas archivadas.",
  );
}

export async function fetchTaskCounts(): Promise<TaskCounts | null> {
  const { data } = await apiClient.GET("/api/tasks/summary");
  return data ?? null;
}

export async function fetchTagCatalog(): Promise<TagPublic[]> {
  const { data } = await apiClient.GET("/api/tags");
  return data ?? [];
}

export function createTask(
  text: string,
  tags: string[] = [],
): Promise<TaskActionResult> {
  return runTaskAction(
    () => apiClient.POST("/api/tasks", { body: { text, tags } }),
    "No se pudo crear la tarea.",
  );
}

export function editTaskTags(
  taskId: number,
  tags: string[],
): Promise<TaskActionResult> {
  return runTaskAction(
    () =>
      apiClient.PATCH("/api/tasks/{task_id}/tags", {
        params: { path: { task_id: taskId } },
        body: { tags },
      }),
    "No se pudieron guardar las etiquetas.",
  );
}

export async function reorderTasks(taskIds: number[]): Promise<ReorderResult> {
  const { data, error, response } = await apiClient.POST("/api/tasks/reorder", {
    body: { task_ids: taskIds },
  });
  if (data) {
    return { ok: true, tasks: data };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo reordenar la lista."),
  };
}

export function archiveTask(taskId: number): Promise<TaskActionResult> {
  // Body-less POST: the generated client sends no body, so `csrf_guard`
  // (see `src/auth/client.ts`'s `logoutUser`) needs the header spelled out.
  return runTaskAction(
    () =>
      apiClient.POST("/api/tasks/{task_id}/archive", {
        params: { path: { task_id: taskId } },
        headers: { "Content-Type": "application/json" },
      }),
    "No se pudo archivar la tarea.",
  );
}

export function unarchiveTask(taskId: number): Promise<TaskActionResult> {
  // Body-less POST, same csrf_guard header requirement as archiveTask.
  return runTaskAction(
    () =>
      apiClient.POST("/api/tasks/{task_id}/unarchive", {
        params: { path: { task_id: taskId } },
        headers: { "Content-Type": "application/json" },
      }),
    "No se pudo desarchivar la tarea.",
  );
}

type RemovableResult = { ok: true } | { ok: false; message: string };
type TasksUpdater = (updater: (previous: TaskPublic[]) => TaskPublic[]) => void;
type RowErrorsUpdater = (
  updater: (previous: Record<number, string>) => Record<number, string>,
) => void;

/**
 * Builds the row-action handler shared by archive/unarchive/delete: each
 * tab owns one instance (its own `setTasks`/`setRowErrors`/count-refresh),
 * and every row action becomes a one-line call instead of re-deriving the
 * same remove-from-list-or-surface-the-message logic per action.
 */
export function createRowActionApplier(
  setTasks: TasksUpdater,
  setRowErrors: RowErrorsUpdater,
  onRemoved: () => void,
) {
  return (taskId: number, result: RemovableResult): void => {
    if (result.ok) {
      setTasks((previous) => previous.filter((task) => task.id !== taskId));
      onRemoved();
      return;
    }
    setRowErrors((previous) => ({ ...previous, [taskId]: result.message }));
  };
}

export async function deleteTask(taskId: number): Promise<DeleteResult> {
  // Body-less DELETE: csrf_guard requires the header on every mutating verb,
  // and a 204 has no JSON body, so success is read off `response.ok`.
  const { error, response } = await apiClient.DELETE("/api/tasks/{task_id}", {
    params: { path: { task_id: taskId } },
    headers: { "Content-Type": "application/json" },
  });
  if (response.ok) {
    return { ok: true };
  }
  return {
    ok: false,
    status: response.status,
    message: extractErrorMessage(error, "No se pudo borrar la tarea."),
  };
}
