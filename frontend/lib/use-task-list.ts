"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { buildTaskListQuery, type TaskFilterState } from "@/lib/task-filter";

type TaskResponseBody = components["schemas"]["TaskResponse"];

export type TaskListKind = "active" | "archived";

export interface TaskListState {
  tasks: TaskResponseBody[];
  activeCount: number;
  archivedCount: number;
  loading: boolean;
  error: string | null;
}

const INITIAL_STATE: TaskListState = {
  tasks: [],
  activeCount: 0,
  archivedCount: 0,
  loading: true,
  error: null,
};

/**
 * Fetches one Task tab's list under the shared filter (Stories 25, 30, 40-45), returning both
 * tab-badge counts every call since the backend always includes both (T7). `requestIdRef` drops
 * a response that arrives after a newer request was already issued (filter changed mid-flight).
 */
export function useTaskList(
  kind: TaskListKind,
  filter: TaskFilterState,
): [TaskListState, () => void] {
  const [state, setState] = useState<TaskListState>(INITIAL_STATE);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    const query = buildTaskListQuery(filter);
    const path = kind === "active" ? "/api/v1/tasks" : "/api/v1/tasks/archived";
    const { data, response } = await apiClient.GET(path, { params: { query } });
    if (requestIdRef.current !== requestId) {
      return;
    }
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (!data) {
      setState((previous) => ({
        ...previous,
        loading: false,
        error: "No se pudo cargar la lista.",
      }));
      return;
    }
    setState({
      tasks: data.tasks,
      activeCount: data.active_count,
      archivedCount: data.archived_count,
      loading: false,
      error: null,
    });
  }, [kind, filter]);

  useEffect(() => {
    void load();
  }, [load]);

  return [state, load];
}
