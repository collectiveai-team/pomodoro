"use client";

import { useEffect, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";

type TaskHistoryResponse = components["schemas"]["TaskHistoryResponse"];

export interface TaskHistoryState {
  history: TaskHistoryResponse | null;
  loading: boolean;
  error: string | null;
}

/**
 * Fetches one Task's whole History for the detail drawer (Stories 33-36). Any failure (the
 * OpenAPI does not type the 404 shape) collapses into one generic message.
 */
export function useTaskHistory(taskId: string): TaskHistoryState {
  const [state, setState] = useState<TaskHistoryState>({
    history: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ history: null, loading: true, error: null });
    async function load() {
      const { data, response } = await apiClient.GET("/api/v1/tasks/{task_id}/history", {
        params: { path: { task_id: taskId } },
      });
      if (cancelled) {
        return;
      }
      if (await redirectToLoginOn401(response)) {
        return;
      }
      if (!data) {
        setState({ history: null, loading: false, error: "No se pudo cargar el detalle." });
        return;
      }
      setState({ history: data, loading: false, error: null });
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  return state;
}
