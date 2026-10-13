"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { components } from "@/lib/api/schema";
import { apiClient } from "@/lib/api-client";
import { redirectToLoginOn401 } from "@/lib/http-session";
import { buildTaskListQuery, type TaskFilterState } from "@/lib/task-filter";

type DayDetailResponse = components["schemas"]["DayDetailResponse"];

export interface DayDetailState {
  detail: DayDetailResponse | null;
  loading: boolean;
  error: string | null;
}

const INITIAL_STATE: DayDetailState = { detail: null, loading: false, error: null };

/**
 * Fetches the selected day's per-Task breakdown (Story 78), filtered by the same shared
 * text+Tag filter as the Tasks tabs (Story 82, T22's `buildTaskListQuery`). `null` `day` means no
 * day is selected yet, so no request is made.
 */
export function useDayDetail(day: string | null, filter: TaskFilterState): DayDetailState {
  const [state, setState] = useState<DayDetailState>(INITIAL_STATE);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    if (!day) {
      setState(INITIAL_STATE);
      return;
    }
    setState((previous) => ({ ...previous, loading: true }));
    const { data, response } = await apiClient.GET("/api/v1/history/day", {
      params: { query: { date: day, ...buildTaskListQuery(filter) } },
    });
    if (requestIdRef.current !== requestId) {
      return;
    }
    if (await redirectToLoginOn401(response)) {
      return;
    }
    if (!data) {
      setState({ detail: null, loading: false, error: "No se pudo cargar el día." });
      return;
    }
    setState({ detail: data, loading: false, error: null });
  }, [day, filter]);

  useEffect(() => {
    void load();
  }, [load]);

  return state;
}
